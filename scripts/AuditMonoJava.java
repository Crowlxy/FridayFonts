import java.awt.Font;
import java.awt.font.FontRenderContext;
import java.awt.font.LineMetrics;
import java.awt.geom.AffineTransform;
import java.io.File;
import java.util.Locale;

/** Load font files privately and measure AWT metrics; does not install fonts or launch a GUI. */
class AuditMonoJava {
    public static void main(String[] args) throws Exception {
        FontRenderContext context = new FontRenderContext(new AffineTransform(), true, true);
        System.out.printf(Locale.ROOT, "Java %s; vendor %s%n", System.getProperty("java.version"), System.getProperty("java.vendor"));
        for (String path : args) {
            Font font = Font.createFont(Font.TRUETYPE_FONT, new File(path)).deriveFont(20f);
            LineMetrics metrics = font.getLineMetrics("SUS430-2D gpy 日本語", context);
            System.out.printf(Locale.ROOT,
                "%s\tascent=%.4f\tdescent=%.4f\tleading=%.4f\theight=%.4f\tadvance=%.4f%n",
                new File(path).getName(), metrics.getAscent(), metrics.getDescent(), metrics.getLeading(),
                metrics.getHeight(), font.getStringBounds("SUS430-2D", context).getWidth());
        }
    }
}
