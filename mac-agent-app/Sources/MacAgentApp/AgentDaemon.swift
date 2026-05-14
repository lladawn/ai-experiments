import Foundation

final class AgentDaemon {
    private let config: AppConfig
    private var process: Process?

    init(config: AppConfig) {
        self.config = config
    }

    func start() {
        healthCheck { [weak self] isRunning in
            guard !isRunning else { return }
            self?.launchDaemon()
        }
    }

    func stop() {
        process?.terminate()
        process = nil
    }

    func submit(task: String) {
        let trimmed = task.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        var request = URLRequest(url: config.taskURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["task": trimmed])

        URLSession.shared.dataTask(with: request).resume()
    }

    private func launchDaemon() {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/bin/zsh")
        proc.arguments = [config.daemonScript.path]
        proc.environment = [
            "MAC_AGENT_MODEL": config.model,
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        ]
        proc.currentDirectoryURL = config.repoRoot

        do {
            try proc.run()
            process = proc
        } catch {
            NSLog("Failed to launch context overlay daemon: \(error)")
        }
    }

    private func healthCheck(completion: @escaping (Bool) -> Void) {
        let url = URL(string: "http://\(config.host):\(config.port)/state")!
        URLSession.shared.dataTask(with: url) { _, response, _ in
            let http = response as? HTTPURLResponse
            completion(http?.statusCode == 200)
        }.resume()
    }
}
