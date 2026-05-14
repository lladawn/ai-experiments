-- Hammerspoon snippet: show the Mac Agent overlay and press E twice
-- quickly to run the Mac Agent Voice shortcut.
--
-- Setup:
-- 1. Install Hammerspoon and grant Accessibility permission.
-- 2. Create a macOS Shortcut named "Mac Agent Voice".
-- 3. In that Shortcut:
--    - Dictate Text
--    - Run Shell Script:
--      /Users/dawn/Code/ai-experiments/mac-agent-runtime/scripts/run-voice-task.sh "$SHORTCUT_INPUT"
-- 4. Start the overlay daemon:
--    /Users/dawn/Code/ai-experiments/mac-agent-runtime/scripts/start-overlay-daemon.sh
-- 5. Paste this file into ~/.hammerspoon/init.lua or require it from there.

local lastE = 0
local thresholdSeconds = 0.35
local shortcutName = "Mac Agent Voice"
local overlayUrl = "http://127.0.0.1:8765"

local screen = hs.screen.primaryScreen()
local frame = screen:frame()
local overlay = hs.webview.new({
  x = frame.x + frame.w - 500,
  y = frame.y + 44,
  w = 480,
  h = math.min(620, frame.h - 88),
})

overlay:url(overlayUrl)
overlay:windowStyle({ "nonactivating", "utility", "HUD" })
overlay:level(hs.drawing.windowLevels.floating)
overlay:allowTextEntry(false)
overlay:closeOnEscape(false)
overlay:bringToFront(false)
overlay:show()

local function runVoiceShortcut()
  hs.execute('/usr/bin/shortcuts run "' .. shortcutName .. '"', true)
end

local tap = hs.eventtap.new({ hs.eventtap.event.types.keyDown }, function(event)
  local key = hs.keycodes.map[event:getKeyCode()]
  local flags = event:getFlags()

  if key ~= "e" or flags.cmd or flags.alt or flags.ctrl or flags.shift then
    return false
  end

  local now = hs.timer.secondsSinceEpoch()
  if now - lastE <= thresholdSeconds then
    lastE = 0
    runVoiceShortcut()
    return true
  end

  lastE = now
  return false
end)

tap:start()
