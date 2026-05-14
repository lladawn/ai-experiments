import AppKit

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private let config = AppConfig()
    private lazy var daemon = AgentDaemon(config: config)
    private lazy var overlay = OverlayWindowController(config: config)
    private lazy var voice = VoiceCommandController(config: config)
    private lazy var commandPanel = CommandPanelController(daemon: daemon, overlay: overlay, voice: voice)
    private var hotkey: DoublePressHotkey?
    private var statusItem: NSStatusItem?
    private var permissionTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        AppLog.write("app launched bundlePath=\(Bundle.main.bundlePath)")
        AppLog.write("bundle id=\(Bundle.main.bundleIdentifier ?? "nil")")
        daemon.start()
        overlay.show()
        setupStatusItem()
        Permissions.promptForAccessibility()

        hotkey = DoublePressHotkey(key: "e") { [weak self] in
            self?.commandPanel.show()
        }
        if hotkey?.start() != true {
            overlay.showPermissionNeeded()
        }
        startPermissionPolling()
    }

    func applicationWillTerminate(_ notification: Notification) {
        permissionTimer?.invalidate()
        hotkey?.stop()
        daemon.stop()
    }

    private func setupStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        item.button?.title = "Context"

        let menu = NSMenu()
        menu.addItem(makeMenuItem(title: "Command...", action: #selector(commandNow)))
        menu.addItem(makeMenuItem(title: "Try Speech Directly", action: #selector(listenNow)))
        menu.addItem(makeMenuItem(title: "Type Command", action: #selector(typeCommand)))
        menu.addItem(makeMenuItem(title: "Show Overlay", action: #selector(showOverlay)))
        menu.addItem(makeMenuItem(title: "Hide Overlay", action: #selector(hideOverlay)))
        menu.addItem(makeMenuItem(title: "Check Permissions", action: #selector(checkPermissions)))
        menu.addItem(makeMenuItem(title: "Request Microphone Permission", action: #selector(requestMicrophonePermission)))
        menu.addItem(makeMenuItem(title: "Open Accessibility Settings", action: #selector(openAccessibilitySettings)))
        menu.addItem(makeMenuItem(title: "Open Microphone Settings", action: #selector(openMicrophoneSettings)))
        menu.addItem(makeMenuItem(title: "Open Speech Recognition Settings", action: #selector(openSpeechRecognitionSettings)))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(makeMenuItem(title: "Open Overlay in Browser", action: #selector(openOverlay)))
        menu.addItem(makeMenuItem(title: "Quit", action: #selector(quit), keyEquivalent: "q"))
        item.menu = menu

        statusItem = item
    }

    private func beginVoiceCommand() {
        beginVoiceCommand(requireAccessibility: false)
    }

    private func beginVoiceCommand(requireAccessibility: Bool) {
        AppLog.write("beginVoiceCommand requireAccessibility=\(requireAccessibility)")
        overlay.show()
        if !Permissions.isAccessibilityTrusted() {
            if requireAccessibility {
                overlay.showPermissionNeeded()
                Permissions.promptForAccessibility()
                return
            }
            overlay.showStatusMessage("Menu listening works; double-E still needs Accessibility")
        }
        overlay.markListening()
        voice.listenOnce(
            onPartial: { [weak self] transcript in
                AppLog.write("partial transcript: \(transcript)")
                self?.overlay.showLiveTranscript(transcript)
            },
            completion: { [weak self] result in
                self?.overlay.markIdle()

                switch result {
                case .success(let command):
                    AppLog.write("voice success: \(command)")
                    self?.overlay.showTranscript(command)
                    self?.daemon.submit(task: command)
                case .failure(let error):
                    AppLog.write("voice failure: \(error.localizedDescription)")
                    self?.overlay.showError(error.localizedDescription)
                }
            }
        )
    }

    @objc private func listenNow() {
        AppLog.write("listenNow menu action entered")
        beginVoiceCommand()
    }

    @objc private func commandNow() {
        AppLog.write("commandNow menu action entered")
        commandPanel.show()
    }

    @objc private func typeCommand() {
        overlay.show()
        let alert = NSAlert()
        alert.messageText = "Mac Agent"
        alert.informativeText = "Enter a command for the local agents."
        alert.addButton(withTitle: "Run")
        alert.addButton(withTitle: "Cancel")

        let input = NSTextField(frame: NSRect(x: 0, y: 0, width: 420, height: 24))
        input.placeholderString = "Open Notion"
        alert.accessoryView = input

        if alert.runModal() == .alertFirstButtonReturn {
            let command = input.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !command.isEmpty else { return }
            overlay.showTranscript(command)
            daemon.submit(task: command)
        }
    }

    @objc private func showOverlay() {
        overlay.show()
    }

    @objc private func hideOverlay() {
        overlay.hide()
    }

    @objc private func openOverlay() {
        NSWorkspace.shared.open(config.overlayURL)
    }

    @objc private func openAccessibilitySettings() {
        Permissions.openPrivacySettings()
    }

    @objc private func openMicrophoneSettings() {
        Permissions.openMicrophoneSettings()
    }

    @objc private func openSpeechRecognitionSettings() {
        Permissions.openSpeechRecognitionSettings()
    }

    @objc private func checkPermissions() {
        overlay.showStatusMessage(Permissions.statusSummary())
    }

    @objc private func requestMicrophonePermission() {
        overlay.showStatusMessage("Requesting microphone permission...")
        Permissions.requestMicrophonePermission { [weak self] granted in
            if granted {
                self?.overlay.showStatusMessage("Microphone granted")
            } else {
                self?.overlay.showError("Microphone not granted")
            }
        }
    }

    @objc private func quit() {
        NSApplication.shared.terminate(nil)
    }

    private func makeMenuItem(title: String, action: Selector, keyEquivalent: String = "") -> NSMenuItem {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: keyEquivalent)
        item.target = self
        return item
    }

    private func startPermissionPolling() {
        permissionTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.refreshHotkeyIfAllowed()
            }
        }
    }

    private func refreshHotkeyIfAllowed() {
        guard Permissions.isAccessibilityTrusted() else { return }
        if hotkey?.isRunning != true {
            if hotkey?.start() == true {
                overlay.showStatusMessage("Double-E is ready")
            }
        }
    }
}
