# OMEGA acceptance tracking

The OMEGA request is an acceptance specification, not a description of a completed
release. PR #46 contains focused studio changes. Do not label the entire request
complete based on passing fixture tests or an installer build.

| Area | Evidence from this change | Remaining acceptance work |
| --- | --- | --- |
| Existing application | Real local server smoke and updater roundtrip; existing model, voice, desktop and device regressions | Long-running use on the user's Windows installation |
| Studio persistence | Shared save completion, dirty-edit protection, revision tests and real-browser history restore passed | Failure recovery under lost connection and concurrent-session soak testing |
| Measured editing | Furniture ID, name, X/Y, width/depth/height and angle submitted through native transactions; browser exercised editing | Complete room/wall/level inspector, grouping, floor duplication, roof and open-kitchen workflows |
| 3D visibility | Native geometry, new-room ceilings hidden, elevated initial camera; corresponding source supplied | Photoreal/PBR material workflow, catalog preview cards, wall cuts and visual acceptance of representative large projects |
| Export | Actual SVG download with measured rooms, wall widths and rotated furniture footprints | Per-floor export, additional 3D export formats and professional documentation layouts |
| Display quality | Real-browser plan/camera fit at 1920×1080, 2560×1440 and 3840×2160; manual camera retention, focus labels and reduced-motion styling | Physical Windows DPI, whole-HUD contrast review and GPU FPS |
| Performance | CI timings, shared icon renderer, guarded WebGL buffer resizing and nonblocking telemetry/model discovery | House/undo/redo still take about 17 seconds in software-WebGL CI (previously 31–32); reload-related waits can reach 20–25 seconds; investigate latency, startup/voice p95, idle CPU/RAM and large-project soak |
| Brain and memory | Existing assistant, continuation, model selection and memory regression coverage remains passing | Live Turkish multi-step goals across sessions, model outages and error recovery beyond fixtures |
| Screen and computer control | Existing desktop targeting, observation and approval regressions preserved | Actual Windows UIA applications, multi-monitor DPI, interruption and emergency-stop sessions |
| Voice and personality | Existing listening/voice regression scripts preserved | Real microphone, noise, echo, barge-in, wake words and natural JARVIS/FRIDAY conversations |
| Smart home | Existing state-verification regressions preserved | Connected Home Assistant/MQTT devices; no physical device success is inferred from mocks |
| Continuous checks | Manual/weekly validation workflow prepared; test evidence retained | Schedule becomes active only on default branch after merge; it does not edit or publish code autonomously |
| Windows distribution | Hosted Windows Python 3.13 regressions, server smoke and Inno Setup compilation | Interactive install/uninstall, Windows 10/11 device validation and explicit release promotion |

Full validation details and actual failed-run explanations are retained in
[4.8-studio-validation.md](4.8-studio-validation.md) and
[4.8-viewport-performance.md](4.8-viewport-performance.md). The release version and
updater channel remain unchanged while this work is a draft.
