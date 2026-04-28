angular.module('beamng.apps')
  .directive('normalHmi', [function () {
    return {
      templateUrl: '/ui/modules/apps/NormalHMI/app.html',
      replace: true,
      restrict: 'EA',
      link: function (scope, element) {
        var streamsList = ['electrics', 'engineInfo', 'sensors', 'minimap']
        var requiredStreams = ['electrics', 'engineInfo', 'sensors']
        var gearNames = ['P', 'R', 'N', 'D', '2', '1']
        var clockTimer = null
        var resizeObserver = null
        var baseWidth = 830
        var baseHeight = 350
        var sessionStartOdo = null
        var sessionStartTime = Date.now()
        var persistentKey = 'normalHmiPersistent'
        var persistentState = { rangeKm: 22, totalKm: 1234 }
        var initialPersistentState = { rangeKm: 22, totalKm: 1234 }
        var navPoller = null
        var lastNavDistance = null
        var navLoggedOnce = false
        var lastNavEta = null
        var lastNavHint = null
        var navLogCount = 0
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
        _loadAudioBuffer('normal.mp3', 'normal')
        var currentRoutePhase = 0

        var ROUTE_PHASE_VIA = 1
        var START_TO_VIA_DISTANCE_M = 1700
        var START_TO_VIA_DURATION_S = 240
        var DEFAULT_CRUISE_SPEED_MS = 50 / 3.6

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

        scope.state = {
          navHint: '',
          navDistanceText: '--',
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
          manualDistanceText: '--',
          manualActive: false,
          driveMode: '手动驾驶',
          dateText: '',
          timeText: '',
          temperatureText: '13°C',
          energyStatus: '能耗正常',
          batteryText: '--',
          batteryPercent: 0,
          estRangeText: '--',
          batteryWarn: false,
          energyWarn: false,
          breakdownActive: false
        }

        scope.trip = { totalDistance: null, range: null, avgSpeed: null }
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
          if (navPoller) clearInterval(navPoller)
        })

        // SimpleTripApp removed to prevent conflicts

        scope.toggleManual = function () {
          scope.state.manualActive = !scope.state.manualActive
          scope.state.driveMode = scope.state.manualActive ? '手动驾驶' : '自动驾驶'
        }

        function pad(num) {
          return num < 10 ? '0' + num : '' + num
        }

        function updateClock() {
          var now = new Date()
          scope.state.dateText = now.getFullYear() + '/' + pad(now.getMonth() + 1) + '/' + pad(now.getDate())
          scope.state.timeText = pad(now.getHours()) + ' : ' + pad(now.getMinutes())
        }

        clockTimer = setInterval(function () {
          scope.$evalAsync(updateClock)
        }, 1000)
        updateClock()

        scope.layoutStyle = { '--adaptive-scale': 1 }
        if (typeof ResizeObserver !== 'undefined') {
          resizeObserver = new ResizeObserver(function (entries) {
            var rect = entries[0].contentRect
            var scaleW = rect.width / baseWidth
            var scaleH = rect.height / baseHeight
            var scale = Math.max(0.6, Math.min(1.4, Math.min(scaleW, scaleH)))
            scope.$evalAsync(function () {
              scope.layoutStyle = { '--adaptive-scale': scale }
            })
          })
          resizeObserver.observe(element[0])
        } else {
          function fallbackScale() {
            var rect = element[0].getBoundingClientRect()
            var scaleW = rect.width / baseWidth
            var scaleH = rect.height / baseHeight
            var scale = Math.max(0.6, Math.min(1.4, Math.min(scaleW, scaleH)))
            scope.layoutStyle = { '--adaptive-scale': scale }
          }
          fallbackScale()
          window.addEventListener('resize', fallbackScale)
          scope.$on('$destroy', function () {
            window.removeEventListener('resize', fallbackScale)
          })
        }

        function formatDistance(meters, decimals) {
          if (meters === undefined || meters === null || isNaN(meters)) return '--'
          return UiUnits.buildString('distance', meters, decimals)
        }

        function formatDuration(seconds, showSeconds) {
          if (showSeconds === undefined) showSeconds = true
          if (seconds === undefined || seconds === null || !isFinite(seconds) || seconds < 0) return '--'
          if (showSeconds && seconds < 60) return seconds.toFixed(0) + ' s'
          var mins = Math.round(seconds / 60)
          if (!showSeconds && mins === 0 && seconds > 0) mins = 1
          if (mins < 120) return mins + ' min'
          return (mins / 60).toFixed(1) + ' h'
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

        function updateNav(distanceMeters, speedMs) {
          scope.state.navDistanceText = formatDistance(distanceMeters, 1)
          scope.state.navRemainingText = formatDistance(distanceMeters, 1)
          var hasDistance = distanceMeters !== undefined && distanceMeters !== null
          var etaSeconds = hasDistance ? distanceMeters / DEFAULT_CRUISE_SPEED_MS : null
          etaSeconds = computeNavEta(distanceMeters, etaSeconds)
          lastNavEta = etaSeconds
          scope.state.navEtaText = formatDuration(etaSeconds, false)
        }

        function applyNavFromStreams(streams) {
          var e = streams.electrics || {}
          var dist = e.navDistance || e.navDist || e.navigationDistance
          if (dist !== undefined && dist !== null) {
            lastNavDistance = dist
            updateNav(dist, scope.latestSpeedMs || 0)
          }
          var etaSec = e.navETA || e.navigationETA || e.navigationEta || e.navEta
          etaSec = computeNavEta(dist, etaSec)
          if (etaSec !== undefined && etaSec !== null) {
            lastNavEta = etaSec
            scope.state.navEtaText = formatDuration(etaSec, false)
          }
          var hint = e.navInstruction || e.navigationInstruction || e.navigationText || e.navHint
          if (hint) {
            lastNavHint = hint
            scope.state.navHint = hint
          }
          var limit = e.navSpeedLimit || e.navigationSpeedLimit
          if (limit !== undefined && limit !== null) {
            var limitObj = UiUnits.speed(limit)
            scope.state.speedLimitValue = Math.round(limitObj.val)
            scope.state.speedLimitUnit = limitObj.unit
          }

          if (streams.minimap && streams.minimap.distToTarget && typeof streams.minimap.distToTarget === 'string') {
            var m = streams.minimap.distToTarget.match(/([0-9]+\\.?[0-9]*)/)
            if (m) {
              var parsed = parseFloat(m[1])
              if (!isNaN(parsed)) {
                lastNavDistance = parsed
                updateNav(parsed, scope.latestSpeedMs || 0)
              }
            }
          }
        }

        function updateStatus(speedMs, limitMs) {
          if (!limitMs) {
            scope.state.navStatus = '畅行'
            scope.state.navStatusTone = 'ok'
            scope.state.speedLimitValue = '60'
            scope.state.speedLimitUnit = 'km/h'
            return
          }
          var limit = UiUnits.speed(limitMs)
          scope.state.speedLimitValue = Math.round(limit.val)
          scope.state.speedLimitUnit = limit.unit

          var current = UiUnits.speed(speedMs).val
          if (current > limit.val + 5) {
            scope.state.navStatus = '\u8bf7\u51cf\u901f'
            scope.state.navStatusTone = 'warn'
          } else {
            scope.state.navStatus = '\u7545\u884c'
            scope.state.navStatusTone = 'ok'
          }
        }

        function updateEnergyStatus(congested) {
          if (scope.state.batteryPercent <= 18) {
            scope.state.energyStatus = '能耗增加'
            scope.state.energyWarn = true
            return
          }
          scope.state.energyStatus = congested ? '\u80fd\u8017\u589e\u52a0' : '\u80fd\u8017\u6b63\u5e38'
          scope.state.energyWarn = false
        }

        function updatePersistentMileage(deltaKm) {
          if (!isFinite(deltaKm) || deltaKm < 0) return
          persistentState.rangeKm = initialPersistentState.rangeKm + deltaKm
          persistentState.totalKm = initialPersistentState.totalKm + deltaKm
          try {
            localStorage.setItem(persistentKey, JSON.stringify(persistentState))
          } catch (e) { }
        }

        function pullNavigation() {
          var lua = "(function() "
            + "local ext = rawget(extensions,'ui_apps_navigation') or rawget(extensions,'ui_navigation') or rawget(extensions,'navigation') "
            + "if ext and ext.getData then return ext.getData() end "
            + "local nav = rawget(_G,'navigation') "
            + "if nav and nav.getData then return nav.getData() end "
            + "local gm = rawget(extensions,'core_groundMarkers') "
            + "if gm and gm.routePlanner and gm.routePlanner.path and gm.routePlanner.path[1] then "
            + "  local p1 = gm.routePlanner.path[1] "
            + "  local p2 = gm.routePlanner.path[2] "
            + "  return {"
            + "    distance = p1.distToTarget,"
            + "    distanceLeft = p1.distToTarget,"
            + "    remainingDistance = p1.distToTarget,"
            + "    nextInstructionDistance = p2 and p2.distToTarget or nil,"
            + "    hint = p1.instruction or p1.roadName or p1.name,"
            + "    speedLimit = p1.speedLimit"
            + "  }"
            + "end "
            + "return nil "
            + "end)()"
          bngApi.engineLua(lua, function (data) {
            if (!data) return
            scope.$evalAsync(function () {
              if (navLogCount < 3) {
                navLogCount++
                navLoggedOnce = true
                try {
                  console.warn('[NormalHMI] navigation data sample #' + navLogCount, data)
                } catch (e) { }
              }

              var dist = data.remainingDistance
                || data.distanceLeft
                || data.distance
                || data.nextInstructionDistance
                || data.routeDistanceLeft
                || data.routeRemaining
                || data.routeLeft
                || data.routeDistance

              if (dist !== undefined && dist !== null) {
                lastNavDistance = dist
                updateNav(dist, scope.latestSpeedMs || 0)
              }
              var etaSec = data.etaSeconds || data.timeLeft || data.eta
              etaSec = computeNavEta(dist, etaSec)
              if (etaSec !== undefined && etaSec !== null) {
                lastNavEta = etaSec
                scope.state.navEtaText = formatDuration(etaSec, false)
              }
              if (data.speedLimit) {
                scope.state.speedLimitValue = Math.round(UiUnits.speed(data.speedLimit).val)
                scope.state.speedLimitUnit = UiUnits.speed(data.speedLimit).unit
              }
              if (data.trafficStatus) {
                var congested = (data.trafficStatus == 'congested' || data.trafficStatus == 'heavy')
                scope.state.navStatus = congested ? '拥堵' : '畅行'
                scope.state.navStatusTone = congested ? 'warn' : 'ok'
                updateEnergyStatus(congested)
              }
              var hint = data.hint || data.nextInstruction || data.nextTurnText
              if (hint) {
                lastNavHint = hint
                scope.state.navHint = hint
              }
            })
          })
        }

        navPoller = setInterval(pullNavigation, 1200)
        pullNavigation()

        scope.$on('VehicleReset', function () {
          scope.trip = { totalDistance: null, range: null, avgSpeed: null }
          scope.state.autopDistanceText = '--'
          scope.state.autopTimeText = '--'
          scope.state.rangeSinceChargeText = '22 km'
          sessionStartOdo = null
          sessionStartTime = Date.now()
        })

        scope.$on('streamsUpdate', function (event, streams) {
          for (var i = 0; i < requiredStreams.length; i++) {
            if (!streams[requiredStreams[i]]) return
          }

          scope.$evalAsync(function () {
            scope.latestSpeedMs = streams.electrics.airspeed || streams.electrics.wheelspeed || 0
            currentRoutePhase = streams.electrics.route_phase || 0
            var speedVal = UiUnits.speed(scope.latestSpeedMs)
            scope.state.speedValue = Math.round(speedVal.val)
            scope.state.speedUnit = speedVal.unit

            var gear = streams.electrics.gear
            var gearChar = 'D' // Default to D for all forward gears (M1, S1, 1, 2, etc.)

            if (gear === 'P') gearChar = 'P'
            else if (gear === 'R') gearChar = 'R'
            else if (gear === 'N') gearChar = 'N'
            // Handle numeric gears (manual boxes often stream numbers)
            else if (typeof gear === 'number') {
              if (gear < 0) gearChar = 'R'
              else if (gear === 0) gearChar = 'N'
            }

            scope.state.gear = gearChar

            var limitMs = streams.electrics.speedLimit || streams.electrics.speedLimiter
            updateStatus(scope.latestSpeedMs, limitMs)

            var navDistance = (lastNavDistance !== null && lastNavDistance !== undefined)
              ? lastNavDistance
              : streams.electrics.navDistance
            if (navDistance !== undefined && navDistance !== null) {
              updateNav(navDistance, scope.latestSpeedMs)
            }

            applyNavFromStreams(streams)

            if (lastNavHint) scope.state.navHint = lastNavHint
            if (lastNavEta !== null && lastNavEta !== undefined) {
              scope.state.navEtaText = formatDuration(lastNavEta, false)
            }

            var yawDeg = (streams.sensors && streams.sensors.yaw !== undefined) ? Math.round(streams.sensors.yaw * 180 / Math.PI) : 0
            scope.state.arrowRotation = 'rotate(' + yawDeg + 'deg)'

            scope.state.temperatureText = '13°C'

            var trafficValue = streams.electrics.trafficDensity || streams.electrics.traffic || streams.electrics.aiTraffic || 0
            var congested = trafficValue > 0.6
            scope.state.navStatus = congested ? '拥堵' : '畅行'
            scope.state.navStatusTone = congested ? 'warn' : 'ok'
            updateEnergyStatus(congested)

            if (sessionStartOdo === null && streams.electrics.odometer !== undefined) {
              sessionStartOdo = streams.electrics.odometer
            }
            
            var distDrivenMeters = 0
            if (streams.electrics.odometer !== undefined && sessionStartOdo !== null) {
              var deltaM = streams.electrics.odometer - sessionStartOdo
              if (Math.abs(deltaM) < 0.5) deltaM = 0
              distDrivenMeters = Math.max(0, deltaM)
              
              var deltaKm = distDrivenMeters / 1000
              scope.state.autopDistanceText = formatDistance(distDrivenMeters, 1)
              var elapsed = (Date.now() - sessionStartTime) / 1000
              scope.state.autopTimeText = formatDuration(elapsed)
              updatePersistentMileage(deltaKm)
            }

            scope.state.rangeSinceChargeText = (106 + distDrivenMeters / 1000).toFixed(1) + ' km'
            scope.state.totalMileageText = Math.round(persistentState.totalKm) + ' km'
            scope.state.manualDistanceText = formatDistance(streams.electrics.trip, 1)

            // === 三窗口 SOC 模型 (与 Python 端一致) ===
            var currentBatteryPct = REVERSE_START_BATT

            if (distDrivenMeters <= 0) {
              currentBatteryPct = REVERSE_START_BATT
            } else if (distDrivenMeters < REVERSE_W1_END_DIST) {
              currentBatteryPct = REVERSE_START_BATT - distDrivenMeters * REVERSE_RATE_W1
            } else if (distDrivenMeters < REVERSE_W2_END_DIST) {
              currentBatteryPct = 20.0 - (distDrivenMeters - REVERSE_W1_END_DIST) * REVERSE_RATE_W2
            } else {
              currentBatteryPct = Math.max(0, 10.0 - (distDrivenMeters - REVERSE_W2_END_DIST) * REVERSE_RATE_W3)
            }

            if (currentBatteryPct < 0) currentBatteryPct = 0
            if (currentBatteryPct > REVERSE_START_BATT) currentBatteryPct = REVERSE_START_BATT

            var pct = Math.round(currentBatteryPct)
            scope.state.batteryText = pct + '%'
            scope.state.batteryPercent = currentBatteryPct
            scope.state.batteryWarn = (currentBatteryPct <= 10)

            if (scope.state.batteryPercent <= 18 && !lowBatteryPlayed) {
              lowBatteryPlayed = true
              // _playAudio('warning')
              // Moved to Python-side SOC trigger for more stable playback.
            }
            if (scope.state.batteryPercent <= 10 && !criticalAudioPlayed) {
              criticalAudioPlayed = true
              // _playAudio('normal')
              // Moved to Python-side SOC trigger for more stable playback.
            }

            var estRangeKm = calculateDisplayedRangeKm(currentBatteryPct)
            scope.state.estRangeText = estRangeKm.toFixed(1) + ' km'

            if (streams.electrics.breakdown_active === 1 && !scope.state.breakdownActive) {
              scope.state.breakdownActive = true
            }
          })
        })
      }
    }
  }])