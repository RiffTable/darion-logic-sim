import com.cburch.logisim.proj.Project;
import com.cburch.logisim.proj.ProjectActions;
import java.io.File;

public class LogisimMemoryHarness {
    public static void main(String[] args) throws Exception {
        File circFile = new File(args[0]);
        
        // 1. DUMMY LOAD: Initialize JVM classes and Logisim singletons
        File dummyFile = File.createTempFile("dummy", ".circ");
        dummyFile.deleteOnExit();
        java.nio.file.Files.write(dummyFile.toPath(), "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?><project source=\"3.8.0\" version=\"1.0\"><circuit name=\"main\"/></project>".getBytes());
        Project dummyProj = ProjectActions.doOpenNoWindow(null, dummyFile);
        
        System.gc(); Thread.sleep(50); System.gc();
        long baseMem = Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory();
        
        Project proj = ProjectActions.doOpenNoWindow(null, circFile);
        
        System.gc(); Thread.sleep(50); System.gc();
        long loadedMem = Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory();
        
        double deltaMb = (loadedMem - baseMem) / (1024.0 * 1024.0);
        if (deltaMb < 0.01) deltaMb = 0.01;
        double baseMb = baseMem / (1024.0 * 1024.0);
        
        System.out.println("PROG_MB:" + baseMb);
        System.out.println("MEM_MB:" + deltaMb);
        System.exit(0);
    }
}
