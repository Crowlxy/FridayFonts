using System;using System.IO;using System.Text;using System.Runtime.InteropServices;using System.Collections.Generic;
public static class Mono491GdiAudit {
 [StructLayout(LayoutKind.Sequential)] struct Fixed {public ushort fraction;public short value;}
 [StructLayout(LayoutKind.Sequential)] struct Mat {public Fixed a,b,c,d;}
 [StructLayout(LayoutKind.Sequential)] struct Point {public int x,y;}
 [StructLayout(LayoutKind.Sequential)] struct GM {public uint w,h;public Point origin;public short advanceX,advanceY;}
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] struct TM {public int height,ascent,descent,internalLeading,externalLeading,averageWidth,maximumWidth,weight,overhang,digitizedX,digitizedY;public char first,last,defaultChar,breakChar;public byte italic,underlined,struckOut,pitchAndFamily,charSet;}
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode)]static extern int AddFontResourceEx(string p,uint f,IntPtr r);
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode)]static extern bool RemoveFontResourceEx(string p,uint f,IntPtr r);
 [DllImport("gdi32.dll")]static extern IntPtr CreateCompatibleDC(IntPtr d);
 [DllImport("gdi32.dll")]static extern IntPtr SelectObject(IntPtr d,IntPtr o);
 [DllImport("gdi32.dll")]static extern bool DeleteObject(IntPtr o);
 [DllImport("gdi32.dll")]static extern bool DeleteDC(IntPtr d);
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode)]static extern IntPtr CreateFont(int h,int w,int e,int orientation,int weight,uint italic,uint underline,uint strike,uint charset,uint op,uint cp,uint quality,uint pitch,string family);
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode)]static extern int GetTextFace(IntPtr d,int n,StringBuilder b);
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode)]static extern bool GetTextMetrics(IntPtr d,out TM t);
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode,SetLastError=true)]static extern uint GetGlyphOutline(IntPtr d,uint c,uint format,out GM m,uint size,byte[] data,ref Mat t);
 public static string Run(string path,string family,int weight,int glyphs,bool italic,string output){
  if(AddFontResourceEx(path,0x10,IntPtr.Zero)==0)throw new Exception("Cannot load private font: "+path);
  var dc=CreateCompatibleDC(IntPtr.Zero);var records=new List<string>();int cases=0;var issues=new List<string>();
  try{
   foreach(int size in new int[]{9,10,11,12,13,14,15,16,17,18,20,24,32}){
    var font=CreateFont(-size,0,0,0,weight,italic?1u:0u,0,0,1,0,0,4,0,family);if(font==IntPtr.Zero)throw new Exception("CreateFont failed");var old=SelectObject(dc,font);
    try{
     var face=new StringBuilder(256);GetTextFace(dc,face.Capacity,face);if(face.ToString()!=family)throw new Exception("GDI fallback: "+face);
     TM tm;if(!GetTextMetrics(dc,out tm))throw new Exception("No GDI metrics");if((tm.italic!=0)!=italic || tm.weight!=weight)throw new Exception("GDI style fallback");
     var mat=new Mat {a=new Fixed{value=1},d=new Fixed{value=1}};
     for(int gid=0;gid<glyphs;gid++){
      GM gm;uint length=GetGlyphOutline(dc,(uint)gid,6|0x80,out gm,0,null,ref mat);cases++;
      if(length==0xffffffff){issues.Add("["+size+","+gid+",\"GetGlyphOutline failed\"]");continue;}
      if(length>10000000)throw new Exception("Invalid glyph bitmap size");
      if(length>0){var data=new byte[Math.Max(4096,(int)length*2)];var got=GetGlyphOutline(dc,(uint)gid,6|0x80,out gm,(uint)data.Length,data,ref mat);if(got==0xffffffff)issues.Add("["+size+","+gid+",\"render failed error "+Marshal.GetLastWin32Error()+"\"]");}
     }
     records.Add("{\"size_px\":"+size+",\"ascent\":"+tm.ascent+",\"descent\":"+tm.descent+",\"height\":"+tm.height+",\"internal_leading\":"+tm.internalLeading+"}");
    }finally{SelectObject(dc,old);DeleteObject(font);}
   }
  }finally{DeleteDC(dc);RemoveFontResourceEx(path,0x10,IntPtr.Zero);}
  var json="{\"engine\":\"Windows GDI GetGlyphOutline GRAY8 / private font / not an app screenshot\",\"cases\":"+cases+",\"errors\":["+String.Join(",",issues)+"],\"metrics\":["+String.Join(",",records)+"]}";File.WriteAllText(output,json);return "GDI glyph cases "+cases+" errors "+issues.Count;
 }
}
