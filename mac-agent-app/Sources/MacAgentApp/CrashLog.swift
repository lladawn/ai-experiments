import Foundation

enum CrashLog {
    static func install() {
        NSSetUncaughtExceptionHandler { exception in
            AppLog.write("uncaught exception: \(exception.name.rawValue) \(exception.reason ?? "")")
            AppLog.write("stack: \(exception.callStackSymbols.joined(separator: " | "))")
        }

        signal(SIGABRT) { signal in
            AppLog.write("received signal SIGABRT \(signal)")
            Darwin.exit(signal)
        }
        signal(SIGILL) { signal in
            AppLog.write("received signal SIGILL \(signal)")
            Darwin.exit(signal)
        }
        signal(SIGSEGV) { signal in
            AppLog.write("received signal SIGSEGV \(signal)")
            Darwin.exit(signal)
        }
    }
}
