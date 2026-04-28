angular.module('beamng.apps')
.directive('spatialHmi', ['$timeout', '$interval', function ($timeout, $interval) {
  return {
    templateUrl: '/ui/modules/apps/SpatialHMI/app.html',
    replace: true,
    restrict: 'EA',
    link: function (scope, element) {
      var streamsList = ['electrics', 'engineInfo', 'sensors']
      var requiredStreams = ['electrics', 'engineInfo', 'sensors']
      var clockTimer = null
      var resizeObserver = null
      var baseWidth = 830
      var baseHeight = 350
      var sessionStartOdo = null
      var sessionStartTime = Date.now()
      var persistentKey = 'spatialHmiPersistent'
      var persistentState = { rangeKm: 22, totalKm: 1234 }
      var initialPersistentState = { rangeKm: 22, totalKm: 1234 }
      var navPoller = null
      var lastNavDistance = null
      var lastNavEta = null
      var lastNavHint = null
      var lowBatteryPlayed = false
      var criticalAudioPlayed = false
      var _audioCtx = null
      var _audioBuffers = {}
      var _pendingLoads = []
      function _loadAudioBuffer(url, key) {
        _pendingLoads.push({ url: url, key: key })
      }
      function _doLoad(url, key) {
        fetch(url).then(function(r) { return r.arrayBuffer() })
          .then(function(ab) { return _audioCtx.decodeAudioData(ab) })
          .then(function(buf) { _audioBuffers[key] = buf })
          .catch(function(e) { console.warn('[HMI Audio] load failed:', url, e) })
      }
      function _playAudio(key) {
        if (!_audioCtx || !_audioBuffers[key]) return
        var src = _audioCtx.createBufferSource()
        src.buffer = _audioBuffers[key]
        src.connect(_audioCtx.destination)
        src.start(0)
      }
      function _unlockAudio() {
        if (_audioCtx) return
        _audioCtx = new (window.AudioContext || window.webkitAudioContext)()
        for (var i = 0; i < _pendingLoads.length; i++) {
          _doLoad(_pendingLoads[i].url, _pendingLoads[i].key)
        }
        _pendingLoads = []
        document.removeEventListener('mousedown', _unlockAudio)
        document.removeEventListener('keydown', _unlockAudio)
      }
      document.addEventListener('mousedown', _unlockAudio)
      document.addEventListener('keydown', _unlockAudio)
      _loadAudioBuffer('warning.mp3', 'warning')
      _loadAudioBuffer('spatial.mp3', 'spatial')
      var popupTimer = null
      var keyHandler = null
      var currentRoutePhase = 0

      var ROUTE_PHASE_VIA = 1
      var START_TO_VIA_DISTANCE_M = 1700
      var START_TO_VIA_DURATION_S = 240
      var DEFAULT_CRUISE_SPEED_MS = 35 / 3.6

      var REVERSE_DIST_TO_DETECT = 2300
      var REVERSE_TOTAL_DIST = 4900
      var REVERSE_BREAKDOWN_DIST = 500
      var REVERSE_START_BATT = 30
      var REVERSE_W1_END_DIST = REVERSE_DIST_TO_DETECT - 500
      var REVERSE_W2_END_DIST = REVERSE_DIST_TO_DETECT - 200
      var REVERSE_RATE_W1 = 10.0 / Math.max(REVERSE_W1_END_DIST, 1)
      var REVERSE_RATE_W2 = 10.0 / 300.0
      var REVERSE_W3_DRAIN_DIST = REVERSE_TOTAL_DIST - REVERSE_BREAKDOWN_DIST - REVERSE_W2_END_DIST
      var REVERSE_RATE_W3 = 10.0 / Math.max(REVERSE_W3_DRAIN_DIST, 1)
      var DISPLAY_RANGE_START_KM = 5.0

      function calculateDisplayedRangeKm(batteryPct) {
        var clampedPct = Math.max(0, Math.min(REVERSE_START_BATT, batteryPct || 0))
        return clampedPct * DISPLAY_RANGE_START_KM / REVERSE_START_BATT
      }

      function isAcceptKey(event) {
        return event && (event.key === 'Enter' || event.code === 'Enter' || event.code === 'NumpadEnter' || event.keyCode === 13)
      }

      function focusAcceptButton() {
        $timeout(function () {
          var acceptButton = element[0].querySelector('.charger-popup .popup-btn.accept')
          if (acceptButton && typeof acceptButton.focus === 'function') acceptButton.focus()
        }, 0, false)
      }

      scope.state = {
        navHint: '',
        navRemainingText: '--',
        navEtaText: '--',
        navStatus: '畅行',
        navStatusTone: 'ok',
        speedLimitValue: '60',
        speedLimitUnit: 'km/h',
        arrowRotation: 'rotate(0deg)',
        speedValue: 0,
        speedUnit: 'km/h',
        gear: 'P',
        autopDistanceText: '--',
        autopTimeText: '--',
        rangeSinceChargeText: '22 km',
        totalMileageText: '1234 km',
        dateText: '',
        timeText: '',
        temperatureText: '13°C',
        energyStatus: '能耗正常',
        batteryText: '--',
        batteryPercent: 0,
        estRangeText: '--',
        batteryWarn: false,
        energyWarn: false,
        isHudActive: false,
        isCritical: false,
        showChargerPopup: false,
        popupCountdown: 10,
        routingAccepted: 0,
        drivingAway: false,
        breakdownActive: false,
        frontDistanceRaw: 999,
        frontDistanceText: '-- m'
      }

      scope.latestSpeedMs = 0

      try {
        var saved = localStorage.getItem(persistentKey)
        if (saved) {
          persistentState = JSON.parse(saved)
          initialPersistentState = JSON.parse(saved)
        }
      } catch (e) { }

      StreamsManager.add(streamsList)
      scope.$on('$destroy', function () {
        StreamsManager.remove(streamsList)
        if (clockTimer) clearInterval(clockTimer)
        if (resizeObserver) resizeObserver.disconnect()
        if (navPoller) $interval.cancel(navPoller)
        if (popupTimer) $interval.cancel(popupTimer)
        if (keyHandler) window.removeEventListener('keydown', keyHandler, true)
      })

      function pad(n) { return n < 10 ? '0' + n : '' + n }

      function updateClock() {
        var now = new Date()
        scope.state.dateText = now.getFullYear() + '/' + pad(now.getMonth() + 1) + '/' + pad(now.getDate())
        scope.state.timeText = pad(now.getHours()) + ' : ' + pad(now.getMinutes())
      }
      clockTimer = setInterval(function () { scope.$evalAsync(updateClock) }, 1000)
      updateClock()

      scope.layoutStyle = { '--adaptive-scale': 1 }
      if (typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver(function (entries) {
          var rect = entries[0].contentRect
          var scaleW = rect.width / baseWidth
          var scaleH = rect.height / baseHeight
          var s = Math.max(0.6, Math.min(1.4, Math.min(scaleW, scaleH)))
          scope.$evalAsync(function () { scope.layoutStyle = { '--adaptive-scale': s } })
        })
        resizeObserver.observe(element[0])
      }

      function formatDistance(m) {
        if (m === undefined || m === null || isNaN(m)) return '--'
        return Math.round(m) + ' m'
      }
      function formatDistanceNav(m) {
        if (m === undefined || m === null || isNaN(m)) return '--'
        return m < 1000 ? Math.round(m) + ' m' : (m / 1000).toFixed(1) + ' km'
      }
      function formatDuration(sec) {
        if (sec === undefined || sec === null || !isFinite(sec) || sec < 0) return '--'
        var s = Math.round(sec)
        if (s < 60) return s + ' s'
        return Math.floor(s / 60) + ' min ' + (s % 60) + ' s'
      }
      function formatDurationNav(sec) {
        if (sec === undefined || sec === null || !isFinite(sec) || sec < 0) return '--'
        var mins = Math.round(sec / 60)
        if (mins < 1) return '1 min'
        return mins < 120 ? mins + ' min' : (mins / 60).toFixed(1) + ' h'
      }

      function computeNavEta(distanceMeters, fallbackEtaSeconds) {
        if (currentRoutePhase === ROUTE_PHASE_VIA && distanceMeters !== undefined && distanceMeters !== null && isFinite(distanceMeters)) {
          return distanceMeters * START_TO_VIA_DURATION_S / Math.max(START_TO_VIA_DISTANCE_M, 1)
        }
        if (distanceMeters !== undefined && distanceMeters !== null && isFinite(distanceMeters)) {
          return distanceMeters / DEFAULT_CRUISE_SPEED_MS
        }
        return fallbackEtaSeconds
      }

      function updateNav(dist) {
        scope.state.navRemainingText = formatDistanceNav(dist)
        var etaSeconds = (dist !== undefined && dist !== null) ? dist / DEFAULT_CRUISE_SPEED_MS : null
        etaSeconds = computeNavEta(dist, etaSeconds)
        lastNavEta = etaSeconds
        scope.state.navEtaText = formatDurationNav(etaSeconds)
      }

      function updateStatus(speedMs, limitMs) {
        if (!limitMs) { scope.state.navStatus = '畅行'; scope.state.navStatusTone = 'ok'; scope.state.speedLimitValue = '60'; return }
        var lim = UiUnits.speed(limitMs)
        scope.state.speedLimitValue = Math.round(lim.val)
        scope.state.speedLimitUnit = lim.unit
        var cur = UiUnits.speed(speedMs).val
        scope.state.navStatus = cur > lim.val + 5 ? '请减速' : '畅行'
        scope.state.navStatusTone = cur > lim.val + 5 ? 'warn' : 'ok'
      }

      function updateEnergyStatus(congested) {
        if (scope.state.batteryPercent <= 18) { scope.state.energyStatus = '能耗增加'; scope.state.energyWarn = true; return }
        scope.state.energyStatus = congested ? '能耗增加' : '能耗正常'
        scope.state.energyWarn = false
      }

      function updatePersistentMileage(dk) {
        if (!isFinite(dk) || dk < 0) return
        persistentState.rangeKm = initialPersistentState.rangeKm + dk
        persistentState.totalKm = initialPersistentState.totalKm + dk
        try { localStorage.setItem(persistentKey, JSON.stringify(persistentState)) } catch (e) { }
      }

      function pullNavigation() {
        var lua = "(function() "
          + "local gm = rawget(extensions,'core_groundMarkers') "
          + "if gm and gm.routePlanner and gm.routePlanner.path and gm.routePlanner.path[1] then "
          + "  local p = gm.routePlanner.path[1] "
          + "  return { distance = p.distToTarget, hint = p.instruction or p.roadName or p.name, speedLimit = p.speedLimit } "
          + "end "
          + "return nil "
          + "end)()"
        bngApi.engineLua(lua, function (data) {
          if (!data) return
          scope.$evalAsync(function () {
            if (data.distance !== undefined && data.distance !== null) { lastNavDistance = data.distance; updateNav(data.distance) }
            if (data.speedLimit) { scope.state.speedLimitValue = Math.round(UiUnits.speed(data.speedLimit).val); scope.state.speedLimitUnit = UiUnits.speed(data.speedLimit).unit }
            if (data.hint) { lastNavHint = data.hint; scope.state.navHint = data.hint }
          })
        })
      }
      navPoller = $interval(pullNavigation, 1200)
      pullNavigation()

      // --- 充电弹窗: 接受 (Enter → 通知Python改道) ---
      scope.acceptCharger = function () {
        if (!scope.state.showChargerPopup) return
        scope.state.showChargerPopup = false
        if (popupTimer) { $interval.cancel(popupTimer); popupTimer = null }
        // 通过vehicle lua设置electrics (engine lua无法直接访问electrics)
        bngApi.engineLua("be:getPlayerVehicle(0):queueLuaCommand('electrics.values.routing_accepted = 1; electrics.values.show_charger_popup = 0')")
        console.log('[SpatialHMI] 用户接受, 改道充电站')
      }

      scope.handlePopupKeydown = function (event) {
        if (!scope.state.showChargerPopup || !isAcceptKey(event)) return
        event.preventDefault()
        event.stopPropagation()
        scope.$evalAsync(function () { scope.acceptCharger() })
      }

      keyHandler = function (e) {
        if (scope.state.showChargerPopup && isAcceptKey(e)) {
          e.preventDefault()
          e.stopPropagation()
          scope.$evalAsync(function () { scope.acceptCharger() })
        }
      }
      window.addEventListener('keydown', keyHandler, true)

      function showChargerPopup() {
        scope.state.showChargerPopup = true
        scope.state.popupCountdown = 10
        focusAcceptButton()
        popupTimer = $interval(function () {
          scope.state.popupCountdown--
          if (scope.state.popupCountdown <= 0) {
            scope.state.showChargerPopup = false
            $interval.cancel(popupTimer); popupTimer = null
            console.log('[SpatialHMI] 弹窗超时, 用户拒绝')
          }
        }, 1000)
      }

      // --- streamsUpdate ---
      scope.$on('streamsUpdate', function (event, streams) {
        for (var i = 0; i < requiredStreams.length; i++) { if (!streams[requiredStreams[i]]) return }
        scope.$evalAsync(function () {
          scope.latestSpeedMs = streams.electrics.airspeed || streams.electrics.wheelspeed || 0
          currentRoutePhase = streams.electrics.route_phase || 0
          var sv = UiUnits.speed(scope.latestSpeedMs)
          scope.state.speedValue = Math.round(sv.val)
          scope.state.speedUnit = sv.unit

          var g = streams.electrics.gear, gc = 'D'
          if (g === 'P') gc = 'P'
          else if (g === 'R') gc = 'R'
          else if (g === 'N') gc = 'N'
          else if (typeof g === 'number') { if (g < 0) gc = 'R'; else if (g === 0) gc = 'N' }
          scope.state.gear = gc

          var limitMs = streams.electrics.speedLimit || streams.electrics.speedLimiter
          updateStatus(scope.latestSpeedMs, limitMs)

          if (lastNavDistance !== null) updateNav(lastNavDistance)
          if (lastNavHint) scope.state.navHint = lastNavHint
          if (lastNavEta !== null) scope.state.navEtaText = formatDurationNav(lastNavEta)

          scope.state.temperatureText = '13°C'

          var traffic = streams.electrics.trafficDensity || streams.electrics.traffic || 0
          var congested = traffic > 0.6
          scope.state.navStatus = congested ? '拥堵' : '畅行'
          scope.state.navStatusTone = congested ? 'warn' : 'ok'
          updateEnergyStatus(congested)

          if (sessionStartOdo === null && streams.electrics.odometer !== undefined) sessionStartOdo = streams.electrics.odometer

          var distDrivenMeters = 0
          if (streams.electrics.odometer !== undefined && sessionStartOdo !== null) {
            var dm = streams.electrics.odometer - sessionStartOdo
            if (Math.abs(dm) < 0.5) dm = 0
            distDrivenMeters = Math.max(0, dm)
            scope.state.autopDistanceText = formatDistance(distDrivenMeters)
            scope.state.autopTimeText = formatDuration((Date.now() - sessionStartTime) / 1000)
            updatePersistentMileage(distDrivenMeters / 1000)
          }

          scope.state.rangeSinceChargeText = (106 + distDrivenMeters / 1000).toFixed(1) + ' km'
          scope.state.totalMileageText = Math.round(persistentState.totalKm) + ' km'

          var fd = streams.electrics.hud_front_dist !== undefined ? streams.electrics.hud_front_dist : 999
          scope.state.frontDistanceRaw = fd
          scope.state.frontDistanceText = fd < 100 ? Math.round(fd) + ' m' : '-- m'

          // 三窗口 SOC
          var bp = streams.electrics.virtual_soc_pct
          if (bp === undefined || bp === null || isNaN(bp)) {
            bp = REVERSE_START_BATT
            if (distDrivenMeters <= 0) bp = REVERSE_START_BATT
            else if (distDrivenMeters < REVERSE_W1_END_DIST) bp = REVERSE_START_BATT - distDrivenMeters * REVERSE_RATE_W1
            else if (distDrivenMeters < REVERSE_W2_END_DIST) bp = 20 - (distDrivenMeters - REVERSE_W1_END_DIST) * REVERSE_RATE_W2
            else bp = Math.max(0, 10 - (distDrivenMeters - REVERSE_W2_END_DIST) * REVERSE_RATE_W3)
          }
          bp = Math.max(0, Math.min(REVERSE_START_BATT, bp))

          scope.state.batteryPercent = bp
          scope.state.batteryText = Math.round(bp) + '%'
          scope.state.batteryWarn = (bp <= 10)

          scope.state.routingAccepted = streams.electrics.routing_accepted || 0
          if ((scope.state.routingAccepted > 0 || streams.electrics.show_charger_popup === 0) && scope.state.showChargerPopup) {
            scope.state.showChargerPopup = false
            if (popupTimer) { $interval.cancel(popupTimer); popupTimer = null }
          }
          if (streams.electrics.charger_dist !== undefined) {
            if (scope.state.isCritical && scope.state.routingAccepted != 2 && streams.electrics.charger_dist > 200) scope.state.drivingAway = true
          }

          if (bp <= 18 && !lowBatteryPlayed) {
            lowBatteryPlayed = true
            // _playAudio('warning')
            // Moved to Python-side SOC trigger for more stable playback.
          }

          // SOC ≤ 10% HUD + 弹窗 + 语音
          if (streams.electrics.show_charger_popup === 1 && !scope.state.showChargerPopup) {
            scope.state.isHudActive = true
            scope.state.isCritical = true
            showChargerPopup()
            if (!criticalAudioPlayed) {
              criticalAudioPlayed = true
              // _playAudio('spatial')
              // Moved to Python-side SOC trigger for more stable playback.
            }
          }

          var estRangeKm = calculateDisplayedRangeKm(bp)
          scope.state.estRangeText = estRangeKm.toFixed(1) + ' km'

          if (streams.electrics.breakdown_active === 1 && !scope.state.breakdownActive) scope.state.breakdownActive = true
        })
      })
    }
  }
}]);