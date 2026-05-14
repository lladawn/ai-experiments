import ApplicationServices
import AppKit
import AVFoundation
import Speech

enum Permissions {
    static func isAccessibilityTrusted() -> Bool {
        AXIsProcessTrusted()
    }

    static func promptForAccessibility() {
        let options = ["AXTrustedCheckOptionPrompt": true] as CFDictionary
        _ = AXIsProcessTrustedWithOptions(options)
    }

    static func openPrivacySettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
            NSWorkspace.shared.open(url)
        }
    }

    static func openMicrophoneSettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone") {
            NSWorkspace.shared.open(url)
        }
    }

    static func openSpeechRecognitionSettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_SpeechRecognition") {
            NSWorkspace.shared.open(url)
        }
    }

    static func requestMicrophonePermission(completion: @escaping @MainActor (Bool) -> Void) {
        AppLog.write("requestMicrophonePermission entered")
        AVCaptureDevice.requestAccess(for: .audio) { granted in
            Task { @MainActor in
                AppLog.write("requestMicrophonePermission result: \(granted)")
                completion(granted)
            }
        }
    }

    static func statusSummary() -> String {
        let accessibility = isAccessibilityTrusted() ? "Accessibility granted" : "Accessibility missing"
        let microphone = "Microphone \(describe(AVCaptureDevice.authorizationStatus(for: .audio).rawValue))"
        let speech = "Speech \(describe(SFSpeechRecognizer.authorizationStatus().rawValue))"
        return "\(accessibility) | \(microphone) | \(speech)"
    }

    private static func describe(_ rawValue: Int) -> String {
        switch rawValue {
        case 0:
            return "not determined"
        case 1:
            return "restricted"
        case 2:
            return "denied"
        case 3:
            return "granted"
        default:
            return "unknown"
        }
    }
}
