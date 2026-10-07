// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "Runway",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "RunwayBar", targets: ["RunwayBar"]),
        .library(name: "RunwayCore", targets: ["RunwayCore"]),
    ],
    targets: [
        .target(name: "RunwayCore"),
        .executableTarget(name: "RunwayBar", dependencies: ["RunwayCore"]),
        .testTarget(name: "RunwayCoreTests", dependencies: ["RunwayCore"],
                    resources: [.copy("Fixtures")]),
    ]
)
