package com.team.shop.service;
import com.team.shop.exception.BizException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.web.MockMultipartFile;
import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.nio.file.Path;
import static org.junit.jupiter.api.Assertions.*;
class ImageStorageServiceTest {
    @TempDir Path temp;
    @Test void validPngStoredAndFakeOrMismatchedRejected() throws Exception {
        var out = new ByteArrayOutputStream();
        ImageIO.write(new BufferedImage(1,1,BufferedImage.TYPE_INT_RGB), "png", out);
        var service = new ImageStorageService(temp.toString());
        var bytes = out.toByteArray();
        String stored = service.store(new MockMultipartFile("image", "valid.png", "image/png", bytes));
        assertTrue(service.resolve(stored.substring("/api/images/".length())).toFile().exists());
        service.deleteStored(stored);
        assertThrows(com.team.shop.exception.NotFoundException.class, () -> service.resolve(stored.substring("/api/images/".length())));
        assertThrows(BizException.class, () -> service.store(new MockMultipartFile("image", "wrong.jpg", "image/jpeg", bytes)));
        assertThrows(BizException.class, () -> service.store(new MockMultipartFile("image", "broken.png", "image/png", new byte[]{(byte)137,80,78,71,13,10,26,10})));
        byte[] fake = bytes.clone();
        fake[20] ^= 0x7f;
        assertThrows(BizException.class, () -> service.store(new MockMultipartFile("image", "fake.png", "image/png", fake)));
        byte[] fakeJpeg = {(byte) 255, (byte) 216, (byte) 255, 0, 0, (byte) 255, (byte) 217};
        assertThrows(BizException.class, () -> service.store(new MockMultipartFile("image", "fake.jpg", "image/jpeg", fakeJpeg)));
        assertThrows(BizException.class, () -> service.store(new MockMultipartFile("image", "large.png", "image/png", new byte[5 * 1024 * 1024 + 1])));
    }
}
