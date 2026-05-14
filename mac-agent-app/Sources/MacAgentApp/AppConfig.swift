import Foundation

struct AppConfig {
    let host = "127.0.0.1"
    let port = 8765
    let model = ProcessInfo.processInfo.environment["MAC_AGENT_MODEL"] ?? "gemma4"

    var overlayURL: URL {
        URL(string: "http://\(host):\(port)")!
    }

    var taskURL: URL {
        URL(string: "http://\(host):\(port)/task")!
    }

    var repoRoot: URL {
        URL(fileURLWithPath: "/Users/dawn/Code/ai-experiments/mac-agent-runtime")
    }

    var daemonScript: URL {
        repoRoot.appendingPathComponent("scripts/start-overlay-daemon.sh")
    }
}
