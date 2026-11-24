import AppKit
import Foundation

let base = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
let input = base.appendingPathComponent("landrics_villa_calderra_map_capture.png")
let output = base.appendingPathComponent("landrics_villa_distance_rings.png")
guard let source = NSImage(contentsOf: input),
      let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 1600, pixelsHigh: 900,
                                   bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                                   isPlanar: false, colorSpaceName: .deviceRGB,
                                   bytesPerRow: 0, bitsPerPixel: 0),
      let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
    fatalError("Could not open Atlas screenshot or create output bitmap")
}

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context
source.draw(in: NSRect(x: 0, y: 0, width: 1600, height: 900),
            from: .zero, operation: .copy, fraction: 1)

func ring(_ radius: CGFloat, _ color: NSColor) {
    let bounds = NSRect(x: 800 - radius, y: 450 - radius, width: radius * 2, height: radius * 2)
    let path = NSBezierPath(ovalIn: bounds)
    NSColor(calibratedWhite: 0.10, alpha: 0.85).setStroke()
    path.lineWidth = 9
    path.stroke()
    color.setStroke()
    path.lineWidth = 5
    path.stroke()
}

let inner = NSColor(calibratedRed: 1.0, green: 0.85, blue: 0.31, alpha: 1)
let outer = NSColor(calibratedRed: 1.0, green: 0.42, blue: 0.41, alpha: 1)
ring(332.867, outer)
ring(285.315, inner)

let center = NSBezierPath(ovalIn: NSRect(x: 792, y: 442, width: 16, height: 16))
NSColor.white.setFill(); center.fill()
NSColor(calibratedWhite: 0.1, alpha: 1).setStroke(); center.lineWidth = 3; center.stroke()

let legend = NSBezierPath(roundedRect: NSRect(x: 1188, y: 628, width: 378, height: 167),
                          xRadius: 12, yRadius: 12)
NSColor(calibratedRed: 0.11, green: 0.15, blue: 0.16, alpha: 0.9).setFill()
legend.fill()

func label(_ text: String, x: CGFloat, y: CGFloat, size: CGFloat, bold: Bool = false) {
    let font = bold ? NSFont.boldSystemFont(ofSize: size) : NSFont.systemFont(ofSize: size)
    (text as NSString).draw(at: NSPoint(x: x, y: y),
                            withAttributes: [.font: font, .foregroundColor: NSColor.white])
}

func swatch(y: CGFloat, color: NSColor) {
    let line = NSBezierPath()
    line.move(to: NSPoint(x: 1212, y: y)); line.line(to: NSPoint(x: 1262, y: y))
    color.setStroke(); line.lineWidth = 5; line.stroke()
}

label("Calderra distance rings", x: 1211, y: 760, size: 22, bold: true)
swatch(y: 734, color: inner); label("30 miles · 48 km", x: 1278, y: 726, size: 21)
swatch(y: 696, color: outer); label("35 miles · 56 km", x: 1278, y: 688, size: 21)
label("Straight-line radii; road distance may be longer.", x: 1212, y: 655, size: 16)

context.flushGraphics()
NSGraphicsContext.restoreGraphicsState()
guard let data = bitmap.representation(using: .png, properties: [:]) else { fatalError("PNG encoding failed") }
try data.write(to: output)
print(output.path)
