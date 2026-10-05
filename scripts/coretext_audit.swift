import Foundation
import CoreText
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let root = URL(fileURLWithPath: CommandLine.arguments[1])
let paths = try FileManager.default.contentsOfDirectory(at: root.appendingPathComponent("fonts-v47"), includingPropertiesForKeys:nil).filter{$0.pathExtension == "ttf"}.sorted{$0.lastPathComponent < $1.lastPathComponent}
let width=1500, height=paths.count*155+80
let ctx=CGContext(data:nil,width:width,height:height,bitsPerComponent:8,bytesPerRow:0,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue)!
ctx.setFillColor(CGColor(gray:1,alpha:1));ctx.fill(CGRect(x:0,y:0,width:width,height:height))
var rows=[[String:Any]]()
func line(_ text:String,_ font:CTFont)->CTLine {
    return CTLineCreateWithAttributedString(NSAttributedString(string:text, attributes:[NSAttributedString.Key(kCTFontAttributeName as String):font,NSAttributedString.Key(kCTForegroundColorAttributeName as String):CGColor(gray:0.08,alpha:1)]))
}
for (i,p) in paths.enumerated() {
    var error:Unmanaged<CFError>?
    precondition(CTFontManagerRegisterFontsForURL(p as CFURL,.process,&error),"Register failed: \(String(describing:error))")
    let descriptors=CTFontManagerCreateFontDescriptorsFromURL(p as CFURL) as! [CTFontDescriptor]
    let font=CTFontCreateWithFontDescriptor(descriptors[0],24,nil)
    let ps=CTFontCopyPostScriptName(font) as String
    precondition(ps.hasPrefix("InoriMono"))
    let samples=["Inori Mono 0123456789 0O1Il {} [] == != ->", "あいうえお がぎぐげご パピプペポ 漢字 日本語 𠮟 𨩃", "▲ ▼ ✡ ❂ ◭ ◮ Ỿ ⦅ ⦆ か\u{3099} は\u{309A} か\u{309A} ト\u{309A} A\u{0301} x\u{0301} x\u{0301}\u{0300}"]
    for (j,text) in samples.enumerated() {
        let l=line(text,font)
        let runs=CTLineGetGlyphRuns(l) as! [CTRun]
        for run in runs {
            let attrs=CTRunGetAttributes(run) as NSDictionary
            let used=attrs[kCTFontAttributeName] as! CTFont
            precondition((CTFontCopyPostScriptName(used) as String)==ps,"Fallback \(ps): \(text)")
            var glyphs=[CGGlyph](repeating:0,count:CTRunGetGlyphCount(run));CTRunGetGlyphs(run,CFRange(location:0,length:0),&glyphs)
            precondition(!glyphs.contains(0),"Missing glyph")
        }
        ctx.textPosition=CGPoint(x:30,y:height-80-i*155-j*34);CTLineDraw(l,ctx)
    }
    for (a,b) in [("が","か\u{3099}"),("Á","A\u{0301}"),("AB","A\u{200D}B"),("x","x\u{0301}")] {
        let wa=CTLineGetTypographicBounds(line(a,font),nil,nil,nil)
        let wb=CTLineGetTypographicBounds(line(b,font),nil,nil,nil)
        precondition(abs(wa-wb)<0.01,"width \(a) \(wa) != \(b) \(wb)")
    }
    let label=CTFontCreateWithName("Helvetica" as CFString,12,nil)
    ctx.textPosition=CGPoint(x:30,y:height-42-i*155);CTLineDraw(line(p.lastPathComponent,label),ctx)
    rows.append(["file":p.lastPathComponent,"postscript":ps,"glyphs":CTFontGetGlyphCount(font),"register":true,"sample_fallbacks":0])
}
let out=root.appendingPathComponent("review-v47")
try FileManager.default.createDirectory(at:out,withIntermediateDirectories:true)
try JSONSerialization.data(withJSONObject:rows,options:[.prettyPrinted,.sortedKeys]).write(to:out.appendingPathComponent("coretext-audit.json"))
let dest=CGImageDestinationCreateWithURL(out.appendingPathComponent("coretext-preview.png") as CFURL,UTType.png.identifier as CFString,1,nil)!
CGImageDestinationAddImage(dest,ctx.makeImage()!,nil);precondition(CGImageDestinationFinalize(dest))
print("PASS CoreText: \(paths.count) fonts, registration, no sample fallback, NFC/NFD/zero-width checks, native rendering")
