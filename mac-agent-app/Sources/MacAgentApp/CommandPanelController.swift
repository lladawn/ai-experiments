import AppKit

@MainActor
final class CommandPanelController {
    private let daemon: AgentDaemon
    private let overlay: OverlayWindowController
    private let voice: VoiceCommandController

    init(daemon: AgentDaemon, overlay: OverlayWindowController, voice: VoiceCommandController) {
        self.daemon = daemon
        self.overlay = overlay
        self.voice = voice
    }

    func show() {
        overlay.show()

        let alert = NSAlert()
        alert.messageText = "Mac Agent"
        alert.informativeText = "Type a command, or try native speech capture."
        alert.addButton(withTitle: "Run")
        alert.addButton(withTitle: "Try Speech")
        alert.addButton(withTitle: "Cancel")

        let input = NSTextField(frame: NSRect(x: 0, y: 0, width: 440, height: 28))
        input.placeholderString = "Open Notion"
        alert.accessoryView = input

        let response = alert.runModal()
        if response == .alertFirstButtonReturn {
            submit(input.stringValue)
        } else if response == .alertSecondButtonReturn {
            listenWithSpeech()
        }
    }

    private func submit(_ command: String) {
        let trimmed = command.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        overlay.showTranscript(trimmed)
        daemon.submit(task: trimmed)
    }

    private func listenWithSpeech() {
        AppLog.write("CommandPanelController listenWithSpeech")
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
                    self?.submit(command)
                case .failure(let error):
                    AppLog.write("voice failure: \(error.localizedDescription)")
                    self?.overlay.showError(error.localizedDescription)
                }
            }
        )
    }
}
