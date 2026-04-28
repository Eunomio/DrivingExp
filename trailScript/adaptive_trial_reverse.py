import time
import math
import csv
import os
import collections
import datetime
import numpy as np
try:
    import ntplib as _ntplib
except ImportError:
    _ntplib = None

os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
import pygame
import random
import win32api, win32con, win32gui

from beamngpy import BeamNGpy, Scenario, Vehicle
from beamngpy.sensors import Electrics, Damage, Ultrasonic
from beamngpy import angle_to_quat
from trial_outcome_profile import (
    BREAKDOWN_BUFFER_DIST_M,
    DISPLAY_START_RANGE_M,
    W1_END_DIST_M,
    W2_END_DIST_M,
    calculate_estimated_range_m as calculate_estimated_range_from_soc,
    calculate_virtual_soc as calculate_profile_virtual_soc,
    sample_finish_outcome,
)

# ================= 1. 配置区域 =================
BEAMNG_HOME = r"E:\BeamNGTech\BeamNG.tech.v0.38.3.0"
USER_PATH = os.path.join(BEAMNG_HOME, "userfolder")
LOG_DIR = r"E:\BeamNGTech\cng"

MAP_NAME = "west_coast_usa"
TARGET_SCENARIO_KEY = "adaptive_trial_reverse"

VEHICLE_MODEL = "vivace"
VEHICLE_CONFIG = "vehicles/vivace/experiment.pc"

# --- 反向路线：起点终点互换 ---
POS_START = (-1081.549, -519.220, 104.640)
POS_VIA   = (-917.382, 856.127, 75.945)
POS_END   = (-677.971, 2062.794, 79.040)
TARGET_CHARGER = (-497.187, 140.643, 100.553)
POS_DETECT = (-285.857, 534.404, 75.109)   # 反向路线使用检测点坐标作为参考点
ROT_START = angle_to_quat((0, 0, 200))

# --- SOC 触发阈值 ---
TRIGGER_SOC_30 = 29.8
TRIGGER_SOC_20 = 20.0
TRIGGER_SOC_10 = 10.0

# --- 距离阈值 (反向路线) ---
# start→via = 1.7km, via→end = 3.2km, total = 4.9km
# 窗口定义统一为 0→1800m, 1800→2300m；硬冲结局按 80/20 抽样
DIST_TO_DETECT = 2400
BREAKDOWN_DIST = BREAKDOWN_BUFFER_DIST_M
TOTAL_ROUTE_DIST = 4900.0
W1_END_DIST = W1_END_DIST_M
W2_END_DIST = W2_END_DIST_M

TRIGGER_DIST_VIA = 30.0
TRIGGER_DIST_END = 20.0

BUTTON_ID = 2
TASK_DELAY_SECONDS = 10.0
ROUTE_PHASE_VIA = 1
ROUTE_PHASE_END = 2
ROUTE_PHASE_CHARGER = 3

def queue_navigation_target(bng, target):
    bng.queue_lua_command(
        f"if core_groundMarkers and core_groundMarkers.setPath then core_groundMarkers.setPath(vec3({target[0]}, {target[1]}, {target[2]})) end"
    )


def set_route_phase(vehicle, phase):
    vehicle.queue_lua_command(f"electrics.values.route_phase = {phase}")


def restore_default_route(bng, vehicle, target_name):
    if target_name == "VIA":
        set_route_phase(vehicle, ROUTE_PHASE_VIA)
        queue_navigation_target(bng, POS_VIA)
    else:
        set_route_phase(vehicle, ROUTE_PHASE_END)
        queue_navigation_target(bng, POS_END)


def accept_charger_route(bng, vehicle):
    vehicle.queue_lua_command(
        "electrics.values.routing_accepted = 2; electrics.values.intervention_active = 1; "
        "electrics.values.show_charger_popup = 0; electrics.values.cancel_charger = 0"
    )
    set_route_phase(vehicle, ROUTE_PHASE_CHARGER)
    queue_navigation_target(bng, TARGET_CHARGER)


def reject_charger_route(bng, vehicle, target_name):
    vehicle.queue_lua_command(
        "electrics.values.routing_accepted = 0; electrics.values.intervention_active = 0; "
        "electrics.values.show_charger_popup = 0; electrics.values.cancel_charger = 0"
    )
    restore_default_route(bng, vehicle, target_name)

def calculate_virtual_soc(dist_driven_m, can_finish_without_charger):
    return calculate_profile_virtual_soc(
        dist_driven_m,
        TOTAL_ROUTE_DIST,
        can_finish_without_charger,
        w1_end_dist_m=W1_END_DIST,
        w2_end_dist_m=W2_END_DIST,
        breakdown_buffer_dist_m=BREAKDOWN_DIST,
    )


def calculate_estimated_range_m(virtual_soc_pct):
    return calculate_estimated_range_from_soc(
        virtual_soc_pct,
        display_start_range_m=DISPLAY_START_RANGE_M,
    )

class PeripheralReactionTask:
    def __init__(self, button_id, log_dir):
        self.button_id = button_id
        self.screen_width = 1920
        self.screen_height = 1080
        self.safe_margin = 300
        self.dot_radius = 60
        self.tri_size = 30
        self.colors = {'red': (220, 20, 20), 'blue': (20, 20, 220), 'white': (255, 255, 255)}

        self.interval = 1.5
        self.wait_duration = 15.0
        self.sound_trigger_time = 12.0
        self.response_window = 3.0
        self.show_time = 1.5

        pygame.init()
        pygame.mixer.init()

        try:
            sound_path = os.path.join(os.path.dirname(__file__), "buttonTask.mp3")
            self.sound_alert = pygame.mixer.Sound(sound_path)
        except Exception:
            self.sound_alert = None

        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            self.js = pygame.joystick.Joystick(0)
            self.js.init()

        os.environ['SDL_VIDEO_WINDOW_POS'] = "0, 0"
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.NOFRAME)
        hwnd = pygame.display.get_wm_info()["window"]
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                               win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT)
        win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(0, 0, 0), 0, win32con.LWA_COLORKEY)
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOSIZE)

        if not os.path.exists(log_dir): os.makedirs(log_dir)
        self.csv_path = os.path.join(log_dir, f"reaction_data_{int(time.time())}_adaptive_reverse.csv")
        self.log_file = open(self.csv_path, 'w', newline='')
        self.writer = csv.writer(self.log_file)
        self.writer.writerow(["Timestamp", "Phase", "Stimulus", "Action", "ReactionTime_ms", "IsCorrect"])

        self.active = False
        self.phase_tag = ""
        self.queue = []
        self.state = 0
        self.timer_base = 0
        self.curr_stim = None
        self.curr_pos = (0, 0)
        self.has_acted = False
        self.sound_played = False
        self.first_trial_in_session = False

    def start_session(self, phase_tag, current_time):
        self.active = True
        self.phase_tag = phase_tag
        items = ['red'] * 3 + ['blue'] * 3
        random.shuffle(items)
        self.queue = items
        self.state = 1
        self.timer_base = current_time
        self.has_acted = False
        self.sound_played = False
        self.first_trial_in_session = True

    def update(self, current_time):
        self.screen.fill((0, 0, 0))
        if not self.active:
            pygame.event.pump()
            return
        dt = current_time - self.timer_base
        if self.state == 1:
            current_wait_time = self.wait_duration if self.first_trial_in_session else self.interval
            if self.first_trial_in_session and dt >= self.sound_trigger_time and not self.sound_played:
                if self.sound_alert: self.sound_alert.play()
                self.sound_played = True
            if dt >= current_wait_time:
                if len(self.queue) > 0:
                    self.curr_stim = self.queue.pop(0)
                    self.curr_pos = self._get_random_edge_pos()
                    self.state = 2; self.timer_base = current_time; self.has_acted = False; self.first_trial_in_session = False
                else: self.active = False
        elif self.state == 2:
            if dt < self.show_time and not self.has_acted: self._draw_stimulus(self.curr_stim, self.curr_pos)
            if dt >= self.response_window:
                if not self.has_acted: self._record(current_time, "Timeout")
                if len(self.queue) > 0: self.state = 1; self.timer_base = current_time; self.has_acted = False; self.sound_played = False
                else: self.active = False
        for event in pygame.event.get():
            if event.type == pygame.JOYBUTTONDOWN:
                if event.button == self.button_id:
                    if self.state == 2 and dt < self.show_time and not self.has_acted:
                        self.has_acted = True
                        rt = dt * 1000
                        self._record(current_time, "Press", rt)
        pygame.display.update()

    def _record(self, t, action, rt="NA"):
        is_correct = (action == "Press") if self.curr_stim == 'red' else (action == "Timeout")
        self.writer.writerow([f"{t:.3f}", self.phase_tag, self.curr_stim, action, f"{rt}", is_correct])
        self.log_file.flush()

    def _draw_stimulus(self, color_key, pos):
        pygame.draw.circle(self.screen, self.colors[color_key], pos, self.dot_radius)
        cx, cy = pos
        r = self.tri_size
        pygame.draw.polygon(self.screen, self.colors['white'], [(cx, cy - r), (cx - r, cy + r // 2), (cx + r, cy + r // 2)])

    def _get_random_edge_pos(self):
        margin_w = int(self.screen_width * 0.2); margin_h = int(self.screen_height * 0.2)
        zone = random.randint(0, 3)
        if zone == 0: return random.randint(50, self.screen_width - 50), random.randint(50, margin_h)
        elif zone == 1: return random.randint(50, self.screen_width - 50), random.randint(self.screen_height - margin_h, self.screen_height - 50)
        elif zone == 2: return random.randint(50, margin_w), random.randint(50, self.screen_height - 50)
        else: return random.randint(self.screen_width - margin_w, self.screen_width - 50), random.randint(50, self.screen_height - 50)

    def close(self): self.log_file.close(); pygame.quit()


def main():
    print(">>> 启动 Adaptive HMI 测试 (反向路线，认知敏感型)...")
    reaction_task = None
    bng = BeamNGpy("localhost", 64256, home=BEAMNG_HOME, user=USER_PATH)
    bng.open(launch=True, deploy=True)

    try:
        scenario = Scenario(MAP_NAME, TARGET_SCENARIO_KEY)
        print(">>> 配置车辆与传感器...")
        vehicle = Vehicle("ego_vehicle", model=VEHICLE_MODEL, part_config=VEHICLE_CONFIG)

        electrics = Electrics()
        damage = Damage()
        vehicle.attach_sensor("electrics", electrics)
        vehicle.attach_sensor("damage", damage)

        scenario.add_vehicle(vehicle, pos=POS_START, rot_quat=ROT_START)

        scenario.make(bng)
        bng.load_scenario(scenario)
        bng.start_scenario()

        print(">>> 生成交通流...")
        bng.queue_lua_command("gameplay_traffic.setupTraffic(5, 0, {simpleVehicles=true})")
        bng.queue_lua_command("gameplay_traffic.setTrafficVars({aggression = 0.2})")
        bng.queue_lua_command("gameplay_traffic.activate()")

        vehicle.connect(bng)

        print(">>> 挂载前方超声波雷达...")
        ultrasonic = Ultrasonic("ultrasonic_front", bng, vehicle, pos=(0, -2.2, 0.5), dir=(0, -1, 0))
        ultrasonic.set_is_visualised(False)

        print(">>> 加载 AdaptiveHMI 布局")
        bng.queue_lua_command("core_gamestate.setGameState('freeroam', 'freeroam', 'freeroam')")
        time.sleep(1)
        bng.queue_lua_command("guihooks.trigger('appContainer:loadLayoutByFilename', '/settings/ui_apps/layouts/default/adaptiveHmi.uilayout.json')")
        time.sleep(0.5)

        print(">>> 设置初始导航 (反向路线)...")
        current_target = "VIA"
        set_route_phase(vehicle, ROUTE_PHASE_VIA)
        queue_navigation_target(bng, POS_VIA)
        time.sleep(0.5)

        bng.resume()
        time.sleep(2)

        reaction_task = PeripheralReactionTask(BUTTON_ID, LOG_DIR)
        task_30_state = 0; task_30_timer = 0
        task_post_decision_state = 0; task_post_decision_timer = 0
        reaction_was_active = False

        if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)
        subject_id = input("请输入被试ID [例如: S01_Adaptive_Rev]: ").strip()
        filepath = os.path.join(LOG_DIR, f"log_{subject_id}_adaptive_reverse.csv")
        can_finish_without_charger = sample_finish_outcome()
        if can_finish_without_charger:
            print(">>> 本次硬冲结局采样: 30% 成功，可带电到达终点。")
        else:
            print(">>> 本次硬冲结局采样: 70% 失败，将在终点前 500m 抛锚。")

        headers = [
            "Timestamp", "NTP_Time", "Event_Marker", "Current_Window", "Pos_X", "Pos_Y", "Pos_Z",
            "Speed_kmh", "Speed_SD", "Accel_m_s2", "Accel_SD", "Throttle", "Brake", "Steering",
            "Dist_Object_Front", "TTC", "Collision", "Virtual_SOC_Pct", "Dist_Driven_m",
            "Decision_Result", "Decision_Time_s"
        ]

        speed_window = collections.deque(maxlen=20)
        accel_window = collections.deque(maxlen=20)

        flags = {
            "MARKER_START": False, "MARKER_30": False, "MARKER_20": False,
            "MARKER_10": False, "MARKER_END": False,
            "ROUTING_ACCEPTED": False, "BREAKDOWN": False
        }

        start_odo = None
        current_dist_m = 0.0
        dist_charger_at_alert = None
        intervention_active = False
        driving_away = False
        intervention_start_time = None
        popup_shown = False
        popup_show_time = None
        POPUP_TIMEOUT = 10.0
        decision_time = None
        decision_result = None
        decision_made = False
        enter_was_down = False
        target_before_charger = "VIA"

        print(f">>> 开始记录...")
        _ntp_offset = 0.0
        if _ntplib is not None:
            try:
                _resp = _ntplib.NTPClient().request('pool.ntp.org', version=3)
                _ntp_offset = _resp.offset
                print(f">>> NTP 同步成功，偏移量: {_ntp_offset:.3f}s")
            except Exception as _ntp_err:
                print(f">>> NTP 同步失败，使用本地时钟: {_ntp_err}")
        else:
            print(">>> ntplib 未安装，使用本地时钟作为 NTP_Time")

        def ntp_ts():
            ts = time.time() + _ntp_offset
            ms = int(ts * 1000) % 1000
            dt = datetime.datetime.fromtimestamp(ts)
            return "%04d/%02d/%02d %02d:%02d:%02d.%03d" % (
                dt.year, dt.month, dt.day,
                dt.hour, dt.minute, dt.second, ms
            )

        input("   >>> 按 [Enter] 键开始记录数据 (切回游戏窗口!)...")
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerow(["0.000", ntp_ts(), f"NTP_OFFSET_{_ntp_offset:.6f}s", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])
            writer.writerow(["0.000", ntp_ts(), f"OUTCOME_ROLL_{'FINISH' if can_finish_without_charger else 'BREAKDOWN'}", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])

            start_time = time.time()
            last_time = start_time
            last_speed_ms = 0.0

            while True:
                loop_start = time.time()
                current_t = loop_start - start_time
                dt = loop_start - last_time
                if dt <= 0: dt = 1e-4
                last_time = loop_start
                enter_is_down = bool(win32api.GetAsyncKeyState(win32con.VK_RETURN) & 0x8000)

                vehicle.poll_sensors()

                pos = vehicle.state.get('pos', (0,0,0))
                dir_vec = vehicle.state.get('dir', (0,1,0))
                dist_obj = ultrasonic.poll().get('distance', 999.0) if ultrasonic else 999.0
                if dist_obj > 1000: dist_obj = 999.0

                dist_charger = math.sqrt((pos[0]-TARGET_CHARGER[0])**2 + (pos[1]-TARGET_CHARGER[1])**2)

                # --- 罗盘方向计算 ---
                dx_charger = TARGET_CHARGER[0] - pos[0]
                dy_charger = TARGET_CHARGER[1] - pos[1]
                compass_deg = math.degrees(math.atan2(dx_charger, dy_charger))
                if compass_deg < 0: compass_deg += 360

                dist_detect = math.sqrt((pos[0]-POS_DETECT[0])**2 + (pos[1]-POS_DETECT[1])**2)
                if intervention_active:
                    vehicle.queue_lua_command(f"electrics.values.charger_yaw = {compass_deg:.1f}; electrics.values.charger_dist = {dist_detect:.1f}")
                    if dist_detect > 200 and not driving_away and not decision_made:
                        driving_away = True
                        decision_result = "REJECTED_CHARGER"
                        decision_made = True
                        popup_shown = False
                        intervention_active = False
                        if intervention_start_time is not None:
                            decision_time = current_t - intervention_start_time
                        marker_str = "MARKER_DECISION"
                        reject_charger_route(bng, vehicle, target_before_charger)
                        current_target = target_before_charger
                        print(f"[Adaptive 反向] 离检测点 {dist_detect:.0f}m > 200m，决策: 拒绝。耗时: {decision_time:.1f}s")

                s_elec = vehicle.sensors['electrics']

                routing_acc = s_elec.get('routing_accepted', 0)

                intent_detected = False
                if intervention_active and dist_charger_at_alert is not None and not driving_away:
                    if dist_charger < (dist_charger_at_alert - 100.0):
                        intent_detected = True

                if (routing_acc == 1 or intent_detected) and not flags["ROUTING_ACCEPTED"] and not decision_made:
                    flags["ROUTING_ACCEPTED"] = True
                    popup_shown = False
                    decision_result = "ACCEPTED_CHARGER"
                    decision_made = True
                    if intervention_start_time is not None:
                        decision_time = current_t - intervention_start_time
                    marker_str = "MARKER_DECISION"
                    accept_charger_route(bng, vehicle)
                    current_target = "CHARGER"
                    print(f"[Adaptive 反向] 检测到驶向充电站，决策: 接受。耗时: {decision_time:.1f}s")

                # --- 弹窗超时检测 (10秒无操作 = 接受自动改道) ---
                if popup_shown and not decision_made and popup_show_time is not None:
                    if current_t - popup_show_time >= POPUP_TIMEOUT:
                        popup_shown = False
                        decision_result = "ACCEPTED_CHARGER_AUTO"
                        decision_made = True
                        flags["ROUTING_ACCEPTED"] = True
                        if intervention_start_time is not None:
                            decision_time = current_t - intervention_start_time
                        marker_str = "MARKER_DECISION"
                        accept_charger_route(bng, vehicle)
                        current_target = "CHARGER"
                        print(f"[Adaptive 反向] 弹窗超时({POPUP_TIMEOUT}s)，用户未取消，接受改道。耗时: {decision_time:.1f}s")

                # --- 手柄/键盘取消检测 (弹窗期间按键 = 取消改道) ---
                if popup_shown and not decision_made:
                    pygame.event.pump()
                    for evt in pygame.event.get():
                        if evt.type == pygame.JOYBUTTONDOWN and evt.button == BUTTON_ID:
                            popup_shown = False
                            decision_result = "REJECTED_CHARGER"
                            decision_made = True
                            intervention_active = False
                            if intervention_start_time is not None:
                                decision_time = current_t - intervention_start_time
                            marker_str = "MARKER_DECISION"
                            reject_charger_route(bng, vehicle, target_before_charger)
                            current_target = target_before_charger
                            print(f"[Adaptive 反向] 手柄按键取消改道，决策: 拒绝。耗时: {decision_time:.1f}s")
                    if enter_is_down and not enter_was_down and not decision_made:
                        popup_shown = False
                        decision_result = "REJECTED_CHARGER"
                        decision_made = True
                        intervention_active = False
                        if intervention_start_time is not None:
                            decision_time = current_t - intervention_start_time
                        marker_str = "MARKER_DECISION"
                        reject_charger_route(bng, vehicle, target_before_charger)
                        current_target = target_before_charger
                        print(f"[Adaptive 反向] 键盘 Enter 取消改道，决策: 拒绝。耗时: {decision_time:.1f}s")

                # --- UI 侧取消检测 ---
                cancel_flag = s_elec.get('cancel_charger', 0)
                if cancel_flag == 1 and popup_shown and not decision_made:
                    popup_shown = False
                    decision_result = "REJECTED_CHARGER"
                    decision_made = True
                    intervention_active = False
                    if intervention_start_time is not None:
                        decision_time = current_t - intervention_start_time
                    marker_str = "MARKER_DECISION"
                    reject_charger_route(bng, vehicle, target_before_charger)
                    current_target = target_before_charger
                    print(f"[Adaptive 反向] UI 按钮取消改道，决策: 拒绝。耗时: {decision_time:.1f}s")

                s_dmg = vehicle.sensors['damage']

                speed_ms = s_elec.get('airspeed', 0.0)
                speed_kmh = speed_ms * 3.6

                accel = (speed_ms - last_speed_ms) / dt
                last_speed_ms = speed_ms

                speed_window.append(speed_kmh)
                accel_window.append(accel)
                speed_sd = np.std(speed_window) if len(speed_window) > 1 else 0.0
                accel_sd = np.std(accel_window) if len(accel_window) > 1 else 0.0

                raw_odo = s_elec.get('odometer', 0.0)
                if start_odo is None and raw_odo > 0: start_odo = raw_odo
                current_dist_m = max(0.0, raw_odo - start_odo) if start_odo is not None else 0.0
                virtual_soc = calculate_virtual_soc(current_dist_m, can_finish_without_charger)
                estimated_range_m = calculate_estimated_range_m(virtual_soc)
                vehicle.queue_lua_command(
                    f"electrics.values.virtual_soc_pct = {virtual_soc:.3f}; "
                    f"electrics.values.est_range_km = {estimated_range_m / 1000.0:.3f}"
                )
                ttc = (dist_obj / speed_ms) if speed_ms > 0.1 else 999.0

                # 当前时间窗口
                if virtual_soc > 20:
                    current_window = "W1_BUILD"
                elif virtual_soc > 10:
                    current_window = "W2_CLIFF"
                else:
                    current_window = "W3_INTERVENTION"

                marker_str = ""
                if not flags["MARKER_START"] and speed_kmh > 1.0: marker_str = "MARKER_START"; flags["MARKER_START"] = True

                if task_30_state == 0 and virtual_soc < TRIGGER_SOC_30:
                    task_30_state = 1; task_30_timer = current_t
                if task_30_state == 1 and (current_t - task_30_timer) >= TASK_DELAY_SECONDS:
                    reaction_task.start_session("High_Battery", current_t); task_30_state = 2
                    writer.writerow([f"{current_t:.3f}", ntp_ts(), "REACTION_START_W1", current_window, f"{pos[0]:.3f}", f"{pos[1]:.3f}", f"{pos[2]:.3f}", f"{speed_kmh:.2f}", f"{speed_sd:.3f}", f"{accel:.2f}", f"{accel_sd:.3f}", f"{s_elec.get('throttle',0):.2f}", f"{s_elec.get('brake',0):.2f}", f"{s_elec.get('steering',0):.2f}", f"{dist_obj:.2f}", f"{ttc:.2f}", f"{s_dmg.get('damage',0):.2f}", f"{virtual_soc:.3f}", f"{current_dist_m:.1f}", "", ""])

                if not flags["MARKER_20"] and virtual_soc <= TRIGGER_SOC_20:
                    marker_str = "MARKER_20_CLIFF_START"; flags["MARKER_20"] = True
                    print(f"[W2 开始] SOC 降至 20%，悬崖掉电开始")

                if not flags["MARKER_10"] and virtual_soc <= TRIGGER_SOC_10:
                    marker_str = "MARKER_10_HMI_TRIGGER"; flags["MARKER_10"] = True
                    dist_charger_at_alert = dist_charger
                    intervention_active = True
                    intervention_start_time = current_t
                    driving_away = False
                    popup_shown = True
                    popup_show_time = current_t
                    target_before_charger = current_target
                    print(f"[Adaptive 反向介入] SOC=10%，自动导航至充电站 + 弹窗。距充电站 {dist_charger_at_alert:.1f}m")
                    vehicle.queue_lua_command("electrics.values.intervention_active = 1")
                    vehicle.queue_lua_command("electrics.values.show_charger_popup = 1")
                    set_route_phase(vehicle, ROUTE_PHASE_CHARGER)
                    queue_navigation_target(bng, TARGET_CHARGER)
                    current_target = "CHARGER"

                if task_post_decision_state == 0 and decision_made:
                    task_post_decision_state = 1; task_post_decision_timer = current_t
                if task_post_decision_state == 1 and (current_t - task_post_decision_timer) >= TASK_DELAY_SECONDS:
                    reaction_task.start_session("Post_Decision", current_t); task_post_decision_state = 2
                    writer.writerow([f"{current_t:.3f}", ntp_ts(), "REACTION_START_POST", current_window, f"{pos[0]:.3f}", f"{pos[1]:.3f}", f"{pos[2]:.3f}", f"{speed_kmh:.2f}", f"{speed_sd:.3f}", f"{accel:.2f}", f"{accel_sd:.3f}", f"{s_elec.get('throttle',0):.2f}", f"{s_elec.get('brake',0):.2f}", f"{s_elec.get('steering',0):.2f}", f"{dist_obj:.2f}", f"{ttc:.2f}", f"{s_dmg.get('damage',0):.2f}", f"{virtual_soc:.3f}", f"{current_dist_m:.1f}", "", ""])

                reaction_task.update(current_t)
                if reaction_was_active and not reaction_task.active:
                    end_phase = reaction_task.phase_tag
                    end_marker = f"REACTION_END_{end_phase.upper()}"
                    writer.writerow([f"{current_t:.3f}", ntp_ts(), end_marker, current_window, f"{pos[0]:.3f}", f"{pos[1]:.3f}", f"{pos[2]:.3f}", f"{speed_kmh:.2f}", f"{speed_sd:.3f}", f"{accel:.2f}", f"{accel_sd:.3f}", f"{s_elec.get('throttle',0):.2f}", f"{s_elec.get('brake',0):.2f}", f"{s_elec.get('steering',0):.2f}", f"{dist_obj:.2f}", f"{ttc:.2f}", f"{s_dmg.get('damage',0):.2f}", f"{virtual_soc:.3f}", f"{current_dist_m:.1f}", "", ""])
                reaction_was_active = reaction_task.active

                dist_via = math.sqrt((pos[0]-POS_VIA[0])**2 + (pos[1]-POS_VIA[1])**2)
                dist_end = math.sqrt((pos[0]-POS_END[0])**2 + (pos[1]-POS_END[1])**2)
                dist_charger = math.sqrt((pos[0]-TARGET_CHARGER[0])**2 + (pos[1]-TARGET_CHARGER[1])**2)

                if current_target == "VIA" and dist_via < TRIGGER_DIST_VIA:
                    current_target = "END"
                    set_route_phase(vehicle, ROUTE_PHASE_END)
                    queue_navigation_target(bng, POS_END)
                    print(">>> 导航切换至终点 END (反向)")

                # --- 电量归零抛锚 ---
                if virtual_soc <= 0 and not flags["ROUTING_ACCEPTED"] and not flags["BREAKDOWN"]:
                    flags["BREAKDOWN"] = True
                    print("!!! 电量耗尽，车辆抛锚！任务失败。")
                    vehicle.queue_lua_command("electrics.values.breakdown_active = 1")
                    time.sleep(3)
                    vehicle.queue_lua_command("controller.mainController.setEngineRunning(false)")
                    row = [f"{current_t:.3f}", ntp_ts(), "PAYOFF_0_BREAKDOWN", current_window, f"{pos[0]:.3f}", f"{pos[1]:.3f}", f"{pos[2]:.3f}", f"{speed_kmh:.2f}", f"{speed_sd:.3f}", f"{accel:.2f}", f"{accel_sd:.3f}", f"{s_elec.get('throttle',0):.2f}", f"{s_elec.get('brake',0):.2f}", f"{s_elec.get('steering',0):.2f}", f"{dist_obj:.2f}", f"{ttc:.2f}", f"{s_dmg.get('damage',0):.2f}", f"{virtual_soc:.3f}", f"{current_dist_m:.1f}", f"{decision_result or ''}", f"{decision_time or ''}"]
                    writer.writerow(row)
                    break

                if current_target == "CHARGER" and dist_charger < TRIGGER_DIST_END:
                    print(">>> 已抵达充电站！信任系统，收益 30 元。(反向路线)")
                    row = [f"{current_t:.3f}", ntp_ts(), "PAYOFF_30_CHARGER", current_window, f"{pos[0]:.3f}", f"{pos[1]:.3f}", f"{pos[2]:.3f}", f"{speed_kmh:.2f}", f"{speed_sd:.3f}", f"{accel:.2f}", f"{accel_sd:.3f}", f"{s_elec.get('throttle',0):.2f}", f"{s_elec.get('brake',0):.2f}", f"{s_elec.get('steering',0):.2f}", f"{dist_obj:.2f}", f"{ttc:.2f}", f"{s_dmg.get('damage',0):.2f}", f"{virtual_soc:.3f}", f"{current_dist_m:.1f}", f"{decision_result or ''}", f"{decision_time or ''}"]
                    writer.writerow(row)
                    break

                row = [f"{current_t:.3f}", ntp_ts(), marker_str, current_window, f"{pos[0]:.3f}", f"{pos[1]:.3f}", f"{pos[2]:.3f}", f"{speed_kmh:.2f}", f"{speed_sd:.3f}", f"{accel:.2f}", f"{accel_sd:.3f}", f"{s_elec.get('throttle',0):.2f}", f"{s_elec.get('brake',0):.2f}", f"{s_elec.get('steering',0):.2f}", f"{dist_obj:.2f}", f"{ttc:.2f}", f"{s_dmg.get('damage',0):.2f}", f"{virtual_soc:.3f}", f"{current_dist_m:.1f}", f"{decision_result or ''}", f"{decision_time if decision_time is not None else ''}"]
                writer.writerow(row)
                f.flush()

                if current_target == "END" and dist_end < TRIGGER_DIST_END:
                    if not flags["MARKER_END"]:
                        flags["MARKER_END"] = True
                        print(">>> 成功抵达终点！头铁硬冲成功，收益 50 元。(反向路线)")
                        row = [f"{current_t:.3f}", ntp_ts(), "PAYOFF_50_FINISH", current_window, f"{pos[0]:.3f}", f"{pos[1]:.3f}", f"{pos[2]:.3f}", f"{speed_kmh:.2f}", f"{speed_sd:.3f}", f"{accel:.2f}", f"{accel_sd:.3f}", f"{s_elec.get('throttle',0):.2f}", f"{s_elec.get('brake',0):.2f}", f"{s_elec.get('steering',0):.2f}", f"{dist_obj:.2f}", f"{ttc:.2f}", f"{s_dmg.get('damage',0):.2f}", f"{virtual_soc:.3f}", f"{current_dist_m:.1f}", f"{decision_result or ''}", f"{decision_time if decision_time is not None else ''}"]
                        writer.writerow(row)
                        break

                elapsed = time.time() - loop_start
                enter_was_down = enter_is_down
                if elapsed < 0.05: time.sleep(0.05 - elapsed)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(">>> 测试结束，清理并关闭...")
        if reaction_task is not None:
            try: reaction_task.close()
            except: pass
        if 'bng' in locals(): bng.close()

if __name__ == "__main__":
    main()
