using System;using System.IO;using System.Collections.Generic;using System.Windows;
using System.Windows.Media;using System.Windows.Media.Imaging;
public static class Mono491WpfProof {
 public static string Run(string path,bool jp,double dpi,string output){
  RenderOptions.ProcessRenderMode=System.Windows.Interop.RenderMode.SoftwareOnly;
  var gt=new GlyphTypeface(new Uri(Path.GetFullPath(path)));
  var visual=new DrawingVisual();
  int width=(int)Math.Ceiling(1050*dpi/96),height=(int)Math.Ceiling(410*dpi/96);
  int missing=0,cases=0;
  using(var dc=visual.RenderOpen()){
   dc.DrawRectangle(Brushes.White,null,new Rect(0,0,1050,410));
   string[] texts=jp?new string[]{"0O1Il  {value: 0123456789}  != <= ->  abc XYZ","Café Āā Đđ Ÿſ  ΑβγΩ  АбвЯ  $ € ¥ £","日本語 ひらがな カタカナ 𠮷 きぎ とど フブプ ０１２"}:
                    new string[]{"0O1Il  {value: 0123456789}  != <= ->  abc XYZ","Café Āā Đđ Ÿſ  ΑβγΩ  АбвЯ  $ € ¥ £","┌─┬─┐ ▁▂▃▄▅▆▇█  ←↑→↓  ±×÷−"};
   double y=30;
   foreach(double px in new double[]{12,14,16,20}){
    foreach(string text in texts){
     var glyphs=new List<ushort>();var advances=new List<double>();
     for(int i=0;i<text.Length;i++){
      int cp=char.ConvertToUtf32(text,i);if(cp>65535)i++;
      ushort gid;if(!gt.CharacterToGlyphMap.TryGetValue(cp,out gid)){missing++;gid=0;}
      glyphs.Add(gid);advances.Add(gt.AdvanceWidths[gid]*px);
     }
     var run=new GlyphRun(gt,0,false,px,glyphs,new Point(20,y),advances,null,null,null,null,null,null);
     dc.DrawGlyphRun(Brushes.Black,run);cases++;y+=24;
    }
    y+=18;
   }
  }
  var bitmap=new RenderTargetBitmap(width,height,dpi,dpi,PixelFormats.Pbgra32);bitmap.Render(visual);
  var encoder=new PngBitmapEncoder();encoder.Frames.Add(BitmapFrame.Create(bitmap));
  using(var file=File.Create(output)){encoder.Save(file);}
  if(missing!=0)throw new Exception("Missing characters: "+missing);
  return "WPF direct GlyphRun / SoftwareOnly / DPI "+dpi+" / "+cases+" lines / italic="+gt.Style+" / weight="+gt.Weight+" / source="+gt.FontUri.LocalPath;
 }
}
