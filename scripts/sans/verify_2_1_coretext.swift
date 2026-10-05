import Foundation
import CoreText

let root = URL(fileURLWithPath: CommandLine.arguments[1])
let manifestData = try Data(contentsOf: root.appendingPathComponent("font-manifest.json"))
let manifest = try JSONSerialization.jsonObject(with: manifestData) as! [[String: Any]]
var errors = [String]()
for style in ["Regular", "Medium", "Bold"] {
    let url = root.appendingPathComponent("ttf/FridaySans-\(style).ttf")
    var error: Unmanaged<CFError>?
    guard CTFontManagerRegisterFontsForURL(url as CFURL, .process, &error) else {
        print("Registration failed \(style)"); exit(1)
    }
    let descriptor = (CTFontManagerCreateFontDescriptorsFromURL(url as CFURL) as! [CTFontDescriptor])[0]
    let font = CTFontCreateWithFontDescriptor(descriptor, 16, nil)
    let expectedName = CTFontCopyPostScriptName(font) as String
    func line(_ text: String) -> CTLine {
        CTLineCreateWithAttributedString(NSAttributedString(string: text, attributes: [
            NSAttributedString.Key(kCTFontAttributeName as String): font,
        ]))
    }
    func glyphs(_ text: String) -> [CGGlyph] {
        var result = [CGGlyph]()
        for run in CTLineGetGlyphRuns(line(text)) as! [CTRun] {
            let actual = (CTRunGetAttributes(run) as NSDictionary)[kCTFontAttributeName] as! CTFont
            if (CTFontCopyPostScriptName(actual) as String) != expectedName {
                errors.append("Fallback \(style): \(text)")
            }
            var gs = [CGGlyph](repeating: 0, count: CTRunGetGlyphCount(run))
            CTRunGetGlyphs(run, CFRange(location: 0, length: 0), &gs)
            if gs.contains(0) { errors.append("Missing \(style): \(text)") }
            result += gs
        }
        return result
    }
    let record = manifest.first { ($0["style"] as? String) == style }!
    let pairs = (record["shaping"] as! [String: Any])["ccmp_pairs"] as! [[String: Any]]
    for pair in pairs {
        let text = (pair["base"] as! String) + "\u{309A}"
        let expectedGlyph = CTFontGetGlyphWithName(font, (pair["glyph"] as! String) as CFString)
        if glyphs(text) != [expectedGlyph] { errors.append("ccmp mismatch \(style): \(text)") }
        if !glyphs("X" + text + "キX").contains(expectedGlyph) { errors.append("Context mismatch \(style): \(text)") }
    }
    for text in ["𠮷野家 𠮷田 𠮷\u{E0100}", "あ\u{3099}いう は\u{309A}ひふ", "x\u{0301} A\u{0301}", "設定 Settings 保存 Save 日本語とEnglish"] {
        _ = glyphs(text)
    }
    func width(_ text: String) -> Double { CTLineGetTypographicBounds(line(text), nil, nil, nil) }
    if !(width("AV") < width("A") + width("V") - 0.05) { errors.append("Kerning \(style)") }
    print("\(style): 14 ccmp pairs, neighboring text, Yoshida-name character/UVS, fallback and kerning checked")
}
print(errors.isEmpty ? "CORETEXT 2.1 CHECKS PASSED" : "FAILURES: \(errors)")
exit(errors.isEmpty ? 0 : 1)
