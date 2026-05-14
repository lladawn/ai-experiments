import AppKit
import ApplicationServices

final class DoublePressHotkey {
    private let keyCode: Int64
    private let threshold: TimeInterval
    private let action: @MainActor @Sendable () -> Void
    private var eventTap: CFMachPort?
    private var runLoopSource: CFRunLoopSource?
    private var lastPress: TimeInterval = 0
    var isRunning: Bool {
        eventTap != nil
    }

    init(key: String, threshold: TimeInterval = 0.35, action: @escaping @MainActor @Sendable () -> Void) {
        self.keyCode = Self.keyCode(for: key)
        self.threshold = threshold
        self.action = action
    }

    func start() -> Bool {
        guard eventTap == nil else { return true }
        let mask = CGEventMask(1 << CGEventType.keyDown.rawValue)
        let refcon = UnsafeMutableRawPointer(Unmanaged.passUnretained(self).toOpaque())

        guard let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .listenOnly,
            eventsOfInterest: mask,
            callback: eventTapCallback,
            userInfo: refcon
        ) else {
            return false
        }

        eventTap = tap
        runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        if let runLoopSource {
            CFRunLoopAddSource(CFRunLoopGetMain(), runLoopSource, .commonModes)
        }
        CGEvent.tapEnable(tap: tap, enable: true)
        return true
    }

    func stop() {
        if let tap = eventTap {
            CGEvent.tapEnable(tap: tap, enable: false)
        }
        if let source = runLoopSource {
            CFRunLoopRemoveSource(CFRunLoopGetMain(), source, .commonModes)
        }
        eventTap = nil
        runLoopSource = nil
    }

    fileprivate func handle(_ event: CGEvent) {
        let eventKeyCode = event.getIntegerValueField(.keyboardEventKeycode)
        guard eventKeyCode == keyCode else { return }

        let flags = event.flags
        guard flags.intersection([.maskCommand, .maskAlternate, .maskControl, .maskShift]).isEmpty else {
            return
        }

        let now = Date().timeIntervalSince1970
        if now - lastPress <= threshold {
            lastPress = 0
            Task { @MainActor [action] in
                action()
            }
        } else {
            lastPress = now
        }
    }

    private static func keyCode(for key: String) -> Int64 {
        switch key.lowercased() {
        case "e":
            return 14
        default:
            return 14
        }
    }
}

private let eventTapCallback: CGEventTapCallBack = { _, type, event, refcon in
    guard type == .keyDown, let refcon else {
        return Unmanaged.passUnretained(event)
    }
    let hotkey = Unmanaged<DoublePressHotkey>.fromOpaque(refcon).takeUnretainedValue()
    hotkey.handle(event)
    return Unmanaged.passUnretained(event)
}
