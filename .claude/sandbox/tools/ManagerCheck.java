import java.io.File;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import main.java.ch.mko.fmm.model.enums.Engine;
import main.java.ch.mko.fmm.model.enums.Version;
import main.java.ch.mko.fmm.model.score.HighscoreSettings;
import main.java.ch.mko.fmm.model.score.HighscoreSettings.PhantomMode;
import main.java.ch.mko.fmm.model.score.Phantom;
import main.java.ch.mko.fmm.views.CustomPhantom;

/**
 * Headless check of mhk2_manager's phantom code with the classes of the patch (200 cc, 250 cc,
 * tuning). Run it in an empty scratch folder (it creates data\Phantom there), never in a game
 * folder:
 *
 *   javac -cp <manager.jar> -d <dir> ManagerCheck.java
 *   java -Djava.awt.headless=true -cp <manager.jar>;<dir> ManagerCheck
 *
 * It extracts the source phantoms from the jar, writes runs of every class on track 1 as
 * new-phantom.mhk2 and has the manager archive and stamp them, then lists the phantoms of both
 * phantom modes and copies the selected ones into place, as the manager does.
 */
public class ManagerCheck {
	static int ok, fail;

	static void check(String what, boolean good) {
		System.out.println((good ? "  ok   " : "  FAIL ") + what);
		if (good) ok++; else fail++;
	}

	public static void main(String[] args) throws Exception {
		Path src = Paths.get(Phantom.SOURCE_DIR);
		Files.createDirectories(src);
		for (int c = 1; c <= 3; c++) {
			for (int t = 1; t <= 8; t++) {
				String name = String.format("phantom-%d-%02d.mhk2", c, t);
				try (InputStream in = ManagerCheck.class.getResourceAsStream("/main/java/ch/mko/fmm/source/data/Phantom/" + name)) {
					Files.copy(in, src.resolve(name), StandardCopyOption.REPLACE_EXISTING);
				}
			}
		}
		main.java.ch.mko.fmm.i18n.I18NLocale.updateLocale();	// as MainFrame.main does
		Version.updateGameVersion();
		check("game version known: " + Version.getGameVersion(), Version.getGameVersion() != null);

		System.out.println("== class names");
		List<String> names = new ArrayList<>();
		for (Engine e : Engine.values()) names.add(e.toString());
		System.out.println("  " + names);
		check("six classes, the new ones named", names.size() == 6 && names.contains("200 ccm")
				&& names.contains("250 ccm") && names.contains("Tuning"));

		byte[] template = Files.readAllBytes(src.resolve("phantom-3-01.mhk2"));
		byte[] sourceId = Arrays.copyOfRange(template, 40, 72);
		for (int cls = 2; cls <= 5; cls++) {
			System.out.println("== run in class " + cls + " (" + Engine.values()[cls] + "), track 1");
			byte[] run = template.clone();
			run[76] = 1;
			run[80] = (byte) cls;
			ByteBuffer.wrap(run, 88, 4).order(ByteOrder.LITTLE_ENDIAN).putFloat(100f + cls);
			Path newPhantom = Paths.get(Phantom.DEFAULT_INPUT_PATH);
			Files.write(newPhantom, run);
			newPhantom.toFile().setLastModified(System.currentTimeMillis() - 1000 * cls);
			Phantom p = new Phantom(newPhantom.toString());
			check("read as " + p.getTrackTime().getEngine(), p.getTrackTime().getEngine() == Engine.values()[cls]);
			String backup = p.createDefaultBackupPath();
			p.savePhantom(backup);
			p.savePhantom(p.getDefaultOutputPath());
			byte[] saved = Files.readAllBytes(Paths.get(p.getDefaultOutputPath()));
			Phantom again = new Phantom(p.getDefaultOutputPath());
			check("archived as " + backup, new File(backup).isFile());
			check("main phantom " + p.getDefaultOutputPath() + " has a valid hash", again.isValid());
			byte[] id = Arrays.copyOfRange(saved, 40, 72);
			if (cls <= 2) {
				check("id taken from the source phantom", Arrays.equals(id, sourceId));
			} else {
				byte[] dashes = new byte[32];
				Arrays.fill(dashes, (byte) '-');
				check("id = 32 dashes", Arrays.equals(id, dashes));
			}
		}

		System.out.println("== phantom lists");
		List<CustomPhantom> best = CustomPhantom.getAllPhantoms(PhantomMode.BEST_TIMES, false, false, false, new ArrayList<>());
		check("best times: 24 stock + 3 new-class phantoms, got " + best.size(), best.size() == 27);
		List<CustomPhantom> source = CustomPhantom.getAllPhantoms(PhantomMode.SOURCE, false, false, false, new ArrayList<>());
		check("source mode: the 24 stock ones, got " + source.size(), source.size() == 24);
		HighscoreSettings settings = HighscoreSettings.loadSettings();
		List<CustomPhantom> selected = CustomPhantom.getSelectedPhantoms(settings);
		check("selected phantoms without error: " + selected.size(), selected.size() == 27);
		Files.delete(Paths.get(Phantom.PHANTOM_DIR, "phantom-4-01.mhk2"));
		CustomPhantom.updateShownPhantoms();
		check("phantom-4-01.mhk2 put back in place", Paths.get(Phantom.PHANTOM_DIR, "phantom-4-01.mhk2").toFile().isFile());
		check("no phantom-4-02.mhk2 made up", !Paths.get(Phantom.PHANTOM_DIR, "phantom-4-02.mhk2").toFile().exists());

		System.out.println(ok + " ok, " + fail + " failed");
		System.exit(fail == 0 ? 0 : 1);
	}
}
