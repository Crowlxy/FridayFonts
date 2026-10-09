using System;using System.IO;using System.Text;using System.Runtime.InteropServices;using System.Collections.Generic;
// Ink top/bottom of round vs flat letters through Windows GDI (TrueType hinting
// as GDI applies it), from a privately loaded font.  Not an app screenshot.
public static class FridayGdiHeights {
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
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode)]static extern IntPtr CreateFont(int h,int w,int e,int o,int weight,uint italic,uint u,uint s,uint cs,uint op,uint cp,uint q,uint pitch,string family);
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode)]static extern int GetTextFace(IntPtr d,int n,StringBuilder b);
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode)]static extern bool GetTextMetrics(IntPtr d,out TM t);
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode,SetLastError=true)]static extern uint GetGlyphOutline(IntPtr d,uint c,uint format,out GM m,uint size,byte[] data,ref Mat t);
 static int[] Ink(IntPtr dc,char ch){
  var mat=new Mat{a=new Fixed{value=1},d=new Fixed{value=1}};GM gm;
  uint len=GetGlyphOutline(dc,ch,6,out gm,0,null,ref mat);       // GGO_GRAY8_BITMAP
  if(len==0xffffffff)throw new Exception("GetGlyphOutline failed "+ch);
  return new int[]{gm.origin.y, gm.origin.y-(int)gm.h};             // top, bottom (y up)
 }
 [DllImport("gdi32.dll",SetLastError=true)]static extern uint GetFontData(IntPtr d,uint table,uint offset,byte[] buf,uint n);
 // The font GDI actually draws with must be the file under test, byte for byte: a same-named older face (installed or loaded earlier) would otherwise pass.
 static void RequireSameFont(IntPtr dc,string path){
  uint n=GetFontData(dc,0,0,null,0);if(n==0xffffffff||n==0)throw new Exception("GetFontData failed for "+path);
  var got=new byte[n];if(GetFontData(dc,0,0,got,n)!=n)throw new Exception("GetFontData short read for "+path);
  var want=File.ReadAllBytes(path);
  using(var sha=System.Security.Cryptography.SHA256.Create()){
   if(want.Length!=got.Length||Convert.ToBase64String(sha.ComputeHash(want))!=Convert.ToBase64String(sha.ComputeHash(got)))throw new Exception("GDI selected a different font than "+path+" ("+got.Length+" vs "+want.Length+" bytes)");
  }
 }
 public static string Run(string path,string family,int weight,bool italic,bool isPrivate){
  if(isPrivate && AddFontResourceEx(path,0x10,IntPtr.Zero)==0)throw new Exception("Cannot load "+path);
  var dc=CreateCompatibleDC(IntPtr.Zero);var rows=new List<string>();
  try{
   for(int size=9;size<=32;size++){
    var font=CreateFont(-size,0,0,0,weight,italic?1u:0u,0,0,1,0,0,5,0,family);var old=SelectObject(dc,font);   // CLEARTYPE_QUALITY
    try{
     var face=new StringBuilder(256);GetTextFace(dc,face.Capacity,face);if(face.ToString()!=family)throw new Exception("GDI fallback: "+face);if(isPrivate)RequireSameFont(dc,path);
     TM tm;GetTextMetrics(dc,out tm);
     var H=Ink(dc,'H');var x=Ink(dc,'x');var parts=new List<string>();
     foreach(char c in "COGS"){var v=Ink(dc,c);if(v[0]!=H[0]||v[1]!=H[1])parts.Add("\"cap_"+c+"\":["+(v[0]-H[0])+","+(v[1]-H[1])+"]");}
     foreach(char c in "oces"){var v=Ink(dc,c);if(v[0]!=x[0]||v[1]!=x[1])parts.Add("\"low_"+c+"\":["+(v[0]-x[0])+","+(v[1]-x[1])+"]");}
     rows.Add("\""+size+"\":{\"line\":"+tm.height+",\"off\":{"+String.Join(",",parts)+"}}");
    }finally{SelectObject(dc,old);DeleteObject(font);}
   }
  }finally{DeleteDC(dc);if(isPrivate)RemoveFontResourceEx(path,0x10,IntPtr.Zero);}
  return "{"+String.Join(",",rows)+"}";
 }
}
