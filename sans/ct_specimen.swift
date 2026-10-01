// Text specimen through CoreText.
//
//   swift ct_specimen.swift out.png <px> "<label>|<font.ttf>" ...
//
// Each font is drawn with the same paragraph at the given pixel size (2x
// backing scale), so faces can be compared as running text, not as glyphs.
import Foundation
import CoreText
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let args = CommandLine.arguments
let out = URL(fileURLWithPath: args[1])
let px = CGFloat(Double(args[2])!)
let faces = args.dropFirst(3).map { $0.split(separator: "|", maxSplits: 1).map(String.init) }
let text = [
    "Friday Sans は Inter と Noto Sans JP から作った書体です。",
    "設定 → 一般 → 情報で macOS 15.4 (Build 24E248) を確認する。",
    "Apple の WWDC 2026 では、新しい API と Swift 6.2 が発表された。",
    "ファイル名 Report_2026-10-01.pdf を Downloads フォルダに保存。",
]
let scale: CGFloat = 2
let lineH = px * 1.6, labelH: CGFloat = 18
let blockH = labelH + CGFloat(text.count) * lineH + 14
let W = Int(px * 36 * scale), H = Int((CGFloat(faces.count) * blockH + 20) * scale)
let ctx = CGContext(data: nil, width: W, height: H, bitsPerComponent: 8, bytesPerRow: 0,
                    space: CGColorSpaceCreateDeviceRGB(),
                    bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
ctx.setFillColor(CGColor(gray: 1, alpha: 1)); ctx.fill(CGRect(x: 0, y: 0, width: W, height: H))
ctx.scaleBy(x: scale, y: scale)
func draw(_ s: String, _ f: CTFont, _ x: CGFloat, _ y: CGFloat, _ g: CGFloat) {
    let l = CTLineCreateWithAttributedString(NSAttributedString(string: s, attributes: [
        NSAttributedString.Key(kCTFontAttributeName as String): f,
        NSAttributedString.Key(kCTForegroundColorAttributeName as String): CGColor(gray: g, alpha: 1)]))
    ctx.textPosition = CGPoint(x: x, y: y); CTLineDraw(l, ctx)
}
let label = CTFontCreateWithName("Helvetica" as CFString, 11, nil)
var y = CGFloat(H) / scale - 16
for face in faces {
    let url = URL(fileURLWithPath: face[1])
    let desc = (CTFontManagerCreateFontDescriptorsFromURL(url as CFURL) as! [CTFontDescriptor])[0]
    let font = CTFontCreateWithFontDescriptor(desc, px, nil)
    draw(face[0], label, 12, y - 8, 0.5)
    y -= labelH
    for s in text { y -= lineH * 0.8; draw(s, font, 12, y, 0.05); y -= lineH * 0.2 }
    y -= 14
}
let dest = CGImageDestinationCreateWithURL(out as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, ctx.makeImage()!, nil); CGImageDestinationFinalize(dest)
