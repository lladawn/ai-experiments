import AppKit
import WebKit

final class OverlayWindowController: NSWindowController {
    private let config: AppConfig
    private let webView = WKWebView(frame: .zero)
    private let statusContainer = NSVisualEffectView()
    private let statusLabel = NSTextField(labelWithString: "")

    init(config: AppConfig) {
        self.config = config

        let screenFrame = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        let size = NSSize(width: 480, height: min(620, screenFrame.height - 80))
        let origin = NSPoint(x: screenFrame.maxX - size.width - 20, y: screenFrame.maxY - size.height - 20)
        let window = NSWindow(
            contentRect: NSRect(origin: origin, size: size),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        window.level = .floating
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        window.isOpaque = false
        window.backgroundColor = .clear
        window.hasShadow = true

        super.init(window: window)
        setupContent()
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    func show() {
        webView.load(URLRequest(url: config.overlayURL))
        window?.orderFrontRegardless()
    }

    func hide() {
        window?.orderOut(nil)
    }

    func markListening() {
        showStatus("Listening...", style: .listening)
    }

    func markIdle() {
        hideStatus()
    }

    func showError(_ message: String) {
        showStatus(message, style: .error)
    }

    func showPermissionNeeded() {
        showStatus("Grant Accessibility permission, then double-press E", style: .warning)
    }

    func showStatusMessage(_ message: String) {
        showStatus(message, style: .success)
    }

    func showLiveTranscript(_ command: String) {
        guard !command.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        showStatus("Listening: \(command)", style: .listening)
    }

    func showTranscript(_ command: String) {
        showStatus("Heard: \(command)", style: .success)
    }

    private func setupContent() {
        guard let contentView = window?.contentView else { return }

        webView.translatesAutoresizingMaskIntoConstraints = false
        statusContainer.translatesAutoresizingMaskIntoConstraints = false
        statusLabel.translatesAutoresizingMaskIntoConstraints = false
        statusContainer.material = .hudWindow
        statusContainer.blendingMode = .withinWindow
        statusContainer.state = .active
        statusContainer.wantsLayer = true
        statusContainer.layer?.cornerRadius = 8
        statusContainer.layer?.borderWidth = 1
        statusContainer.layer?.borderColor = NSColor.white.withAlphaComponent(0.22).cgColor
        statusContainer.isHidden = true

        statusLabel.textColor = .white
        statusLabel.font = .systemFont(ofSize: 13, weight: .semibold)
        statusLabel.alignment = .center
        statusLabel.lineBreakMode = .byTruncatingTail

        contentView.addSubview(webView)
        contentView.addSubview(statusContainer)
        statusContainer.addSubview(statusLabel)

        NSLayoutConstraint.activate([
            webView.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
            webView.topAnchor.constraint(equalTo: contentView.topAnchor),
            webView.bottomAnchor.constraint(equalTo: contentView.bottomAnchor),

            statusContainer.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 16),
            statusContainer.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -16),
            statusContainer.bottomAnchor.constraint(equalTo: contentView.bottomAnchor, constant: -16),
            statusContainer.heightAnchor.constraint(equalToConstant: 42),

            statusLabel.leadingAnchor.constraint(equalTo: statusContainer.leadingAnchor, constant: 12),
            statusLabel.trailingAnchor.constraint(equalTo: statusContainer.trailingAnchor, constant: -12),
            statusLabel.centerYAnchor.constraint(equalTo: statusContainer.centerYAnchor)
        ])
    }

    private enum StatusStyle {
        case listening
        case success
        case warning
        case error
    }

    private func showStatus(_ message: String, style: StatusStyle) {
        statusLabel.stringValue = message
        statusContainer.isHidden = false
        switch style {
        case .listening:
            statusContainer.layer?.backgroundColor = NSColor.systemBlue.withAlphaComponent(0.25).cgColor
        case .success:
            statusContainer.layer?.backgroundColor = NSColor.systemGreen.withAlphaComponent(0.25).cgColor
        case .warning:
            statusContainer.layer?.backgroundColor = NSColor.systemOrange.withAlphaComponent(0.28).cgColor
        case .error:
            statusContainer.layer?.backgroundColor = NSColor.systemRed.withAlphaComponent(0.28).cgColor
        }
    }

    private func hideStatus() {
        statusContainer.isHidden = true
        statusLabel.stringValue = ""
    }
}
