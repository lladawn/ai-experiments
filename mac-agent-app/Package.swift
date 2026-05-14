// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "MacAgentApp",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "MacAgentApp", targets: ["MacAgentApp"])
    ],
    targets: [
        .executableTarget(
            name: "MacAgentApp",
            resources: [
                .copy("Resources")
            ],
            linkerSettings: [
                .linkedFramework("AppKit"),
                .linkedFramework("ApplicationServices"),
                .linkedFramework("AVFoundation"),
                .linkedFramework("Speech"),
                .linkedFramework("WebKit")
            ]
        )
    ]
)
