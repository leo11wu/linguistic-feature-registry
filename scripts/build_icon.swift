// Render the supplied SVG with macOS AppKit and export the standard ICNS sizes.
// Usage: xcrun swift scripts/build_icon.swift app/Assets/AppIcon.svg OUTPUT_DIR
import AppKit
import Foundation

guard CommandLine.arguments.count == 3 else {
    fputs("Usage: build_icon.swift INPUT.svg OUTPUT_DIR\n", stderr)
    exit(2)
}
let source = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
let iconset = output.appendingPathComponent("AppIcon.iconset", isDirectory: true)
try FileManager.default.createDirectory(at: iconset, withIntermediateDirectories: true)
guard let image = NSImage(contentsOf: source) else {
    fputs("AppKit could not decode the SVG.\n", stderr)
    exit(1)
}
let entries: [(String, Int)] = [
    ("icon_16x16.png",16),("icon_16x16@2x.png",32),
    ("icon_32x32.png",32),("icon_32x32@2x.png",64),
    ("icon_128x128.png",128),("icon_128x128@2x.png",256),
    ("icon_256x256.png",256),("icon_256x256@2x.png",512),
    ("icon_512x512.png",512),("icon_512x512@2x.png",1024)
]
for (name, pixels) in entries {
    guard let bitmap = NSBitmapImageRep(bitmapDataPlanes:nil,pixelsWide:pixels,pixelsHigh:pixels,
        bitsPerSample:8,samplesPerPixel:4,hasAlpha:true,isPlanar:false,
        colorSpaceName:.deviceRGB,bytesPerRow:0,bitsPerPixel:0),
        let context = NSGraphicsContext(bitmapImageRep:bitmap) else {
        fatalError("Cannot allocate RGBA bitmap")
    }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    context.imageInterpolation = .high
    let bounds = NSRect(x:0,y:0,width:pixels,height:pixels)
    NSColor.clear.set();bounds.fill(using:.copy)
    image.draw(in:bounds,from:.zero,operation:.sourceOver,fraction:1)
    NSGraphicsContext.restoreGraphicsState()
    guard let png = bitmap.representation(using:.png,properties:[:]) else {fatalError("PNG encoding failed")}
    try png.write(to:iconset.appendingPathComponent(name),options:.atomic)
    if pixels == 1024 {try png.write(to:output.appendingPathComponent("AppIcon.png"),options:.atomic)}
}
let process = Process()
process.executableURL = URL(fileURLWithPath:"/usr/bin/iconutil")
process.arguments = ["-c","icns",iconset.path,"-o",output.appendingPathComponent("AppIcon.icns").path]
try process.run();process.waitUntilExit()
guard process.terminationStatus == 0 else {exit(process.terminationStatus)}
print("Generated AppIcon.icns and transparent PNGs at \(output.path)")
