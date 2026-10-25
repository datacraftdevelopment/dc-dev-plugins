// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "__APP__",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "__APP__", targets: ["__APP__"]),
        .library(name: "__APP__Core", targets: ["__APP__Core"]),
    ],
    dependencies: [
        // Updates: pinned exactly, bumped on purpose. make-app.sh copies Sparkle.framework into the app.
        .package(url: "https://github.com/sparkle-project/Sparkle", exact: "2.10.0"),
    ],
    targets: [
        // Logic with no UI, so it tests without a window.
        .target(name: "__APP__Core"),
        .executableTarget(name: "__APP__", dependencies: [
            "__APP__Core",
            .product(name: "Sparkle", package: "Sparkle"),
        ]),
        .testTarget(name: "__APP__CoreTests", dependencies: ["__APP__Core"]),
    ]
)
