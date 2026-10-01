// Friday Sans proof through CoreText, the renderer macOS itself uses.
//
//   swift coretext_proof.swift <sans dir>
//
// Checks: every sample renders from Friday Sans with no fallback, and kerning
// is applied (the run width of "AV" is less than A + V).  Draws each weight
// next to the macOS system pairing it is measured against: SF Pro Text for
// Latin with Hiragino Sans for Japanese.
import Foundation
import CoreText
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let root = URL(fileURLWithPath: CommandLine.arguments[1])
let weights = [("Regular", "W3", "Regular"), ("Medium", "W4", "Medium"), ("Bold", "W6", "Bold")]
let samples = [
    "Friday Sans は、Inter と Noto Sans JP から作った和文書体です。",
    "AVATAR Wave Typography 0123456789 (2026年10月1日)",
    "macOS の UI で「設定」→「一般」を開き、Version 4.7 を確認する。",
]
let px: CGFloat = 26
let width = 1500, rowH = Int(px * 1.7), blockH = Int(26 + px * 1.1) + samples.count * rowH + 12
let height = 40 + weights.count * 2 * blockH
let ctx = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
                    space: CGColorSpaceCreateDeviceRGB(),
                    bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
ctx.setFillColor(CGColor(gray: 1, alpha: 1)); ctx.fill(CGRect(x: 0, y: 0, width: width, height: height))

func line(_ text: String, _ font: CTFont, _ gray: CGFloat = 0.05) -> CTLine {
    CTLineCreateWithAttributedString(NSAttributedString(string: text, attributes: [
        NSAttributedString.Key(kCTFontAttributeName as String): font,
        NSAttributedString.Key(kCTForegroundColorAttributeName as String): CGColor(gray: gray, alpha: 1)]))
}
func width(_ text: String, _ font: CTFont) -> Double {
    CTLineGetTypographicBounds(line(text, font), nil, nil, nil)
}
let label = CTFontCreateWithName("Helvetica" as CFString, 13, nil)
var y = CGFloat(height - 30)
var failures = [String]()
for (style, hira, sf) in weights {
    let url = root.appendingPathComponent("fonts/FridaySans-\(style).ttf")
    var error: Unmanaged<CFError>?
    precondition(CTFontManagerRegisterFontsForURL(url as CFURL, .process, &error), "register \(style)")
    let desc = (CTFontManagerCreateFontDescriptorsFromURL(url as CFURL) as! [CTFontDescriptor])[0]
    let inori = CTFontCreateWithFontDescriptor(desc, px, nil)
    let ps = CTFontCopyPostScriptName(inori) as String
    // macOS system pairing: SF Pro Text, cascading to Hiragino Sans.
    let hiraDesc = CTFontDescriptorCreateWithNameAndSize("HiraginoSans-\(hira)" as CFString, px)
    let sfAttrs: [String: Any] = [kCTFontNameAttribute as String: "SFProText-\(sf)",
                                  kCTFontCascadeListAttribute as String: [hiraDesc]]
    let system = CTFontCreateWithFontDescriptor(CTFontDescriptorCreateWithAttributes(sfAttrs as CFDictionary), px, nil)
    for (name, font) in [("SF Pro Text \(sf) + Hiragino Sans \(hira)", system), ("Friday Sans \(style)", inori)] {
        ctx.textPosition = CGPoint(x: 30, y: y); CTLineDraw(line(name, label, 0.45), ctx)
        y -= 26 + px * 1.1
        for text in samples {
            let l = line(text, font)
            if font === inori {
                for run in CTLineGetGlyphRuns(l) as! [CTRun] {
                    let used = (CTRunGetAttributes(run) as NSDictionary)[kCTFontAttributeName] as! CTFont
                    if (CTFontCopyPostScriptName(used) as String) != ps { failures.append("fallback \(style): \(text)") }
                }
            }
            ctx.textPosition = CGPoint(x: 30, y: y); CTLineDraw(l, ctx)
            y -= CGFloat(rowH)
        }
        y -= 12
    }
    let av = width("AV", inori), a = width("A", inori), v = width("V", inori)
    print(String(format: "%@ kerning AV %.2f vs A+V %.2f -> %@", style, av, a + v, av < a + v - 0.1 ? "applied" : "MISSING"))
    if !(av < a + v - 0.1) { failures.append("no kerning \(style)") }
}
let out = root.appendingPathComponent("previews/coretext-mixed.png")
let dest = CGImageDestinationCreateWithURL(out as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, ctx.makeImage()!, nil); CGImageDestinationFinalize(dest)
print(failures.isEmpty ? "CORETEXT OK" : "FAILURES: \(failures)")
exit(failures.isEmpty ? 0 : 1)
