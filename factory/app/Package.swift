// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "Runway",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "RunwayBar", targets: ["RunwayBar"]),
        .library(name: "RunwayCore", targets: ["RunwayCore"]),
    ],
    dependencies: [
        .package(url: "https://github.com/migueldeicaza/SwiftTerm", exact: "1.20.0"),
    ],
    targets: [
        .target(name: "RunwayCore"),
        .executableTarget(name: "RunwayBar", dependencies: [
            "RunwayCore",
            .product(name: "SwiftTerm", package: "SwiftTerm"),
        ]),
        .testTarget(name: "RunwayCoreTests", dependencies: ["RunwayCore"],
                    resources: [.copy("Fixtures")]),
    ]
)
