package com.team.shop.service;

import com.team.shop.exception.BizException;
import com.team.shop.exception.NotFoundException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import javax.imageio.ImageIO;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

@Service
public class ImageStorageService {
    private static final long MAX_BYTES = 5L * 1024 * 1024;
    private static final Set<String> EXTENSIONS = Set.of("jpg", "jpeg", "png");
    private static final byte[] PNG_END = {0, 0, 0, 0, 73, 69, 78, 68, (byte) 174, 66, 96, (byte) 130};
    private final Path uploadDir;
    public ImageStorageService(@Value("${shop.upload-dir}") String uploadDir) {
        this.uploadDir = Path.of(uploadDir).toAbsolutePath().normalize();
    }
    public String store(MultipartFile file) {
        if (file == null || file.isEmpty()) throw new BizException("请上传商品图片");
        if (file.getSize() > MAX_BYTES) throw new BizException("上传文件过大（上限 5MB）");
        String extension = extensionOf(file.getOriginalFilename());
        if (!EXTENSIONS.contains(extension)) throw new BizException("仅支持 JPG / PNG 格式的图片");
        String expected = extension.equals("png") ? "image/png" : "image/jpeg";
        if (!expected.equalsIgnoreCase(file.getContentType())) throw new BizException("图片类型与扩展名不符");
        byte[] bytes;
        try { bytes = file.getBytes(); }
        catch (IOException e) { throw new BizException("图片读取失败，请重试"); }
        if (bytes.length > MAX_BYTES) throw new BizException("上传文件过大（上限 5MB）");
        boolean png = extension.equals("png");
        if (png ? !isPng(bytes) : !isJpeg(bytes)) throw new BizException("图片内容与扩展名不符或图片不完整");
        try {
            if (ImageIO.read(new ByteArrayInputStream(bytes)) == null) throw new BizException("图片无法解码");
        } catch (IOException e) { throw new BizException("图片无法解码"); }
        String storedName = UUID.randomUUID() + "." + extension;
        try {
            Files.createDirectories(uploadDir);
            Files.write(uploadDir.resolve(storedName), bytes);
        } catch (IOException e) { throw new BizException("图片保存失败，请重试"); }
        return "/api/images/" + storedName;
    }
    /** 仅由服务端生成路径调用，发布事务失败后删除孤儿文件。 */
    public void deleteStored(String imagePath) throws IOException {
        String prefix = "/api/images/";
        if (imagePath == null || !imagePath.startsWith(prefix)) return;
        String filename = imagePath.substring(prefix.length());
        Path path = uploadDir.resolve(filename).normalize();
        if (path.getParent().equals(uploadDir)) Files.deleteIfExists(path);
    }
    public Path resolve(String filename) {
        Path path = uploadDir.resolve(filename).normalize();
        if (!path.startsWith(uploadDir) || !Files.isRegularFile(path)) throw new NotFoundException("图片不存在");
        return path;
    }
    private boolean isJpeg(byte[] b) {
        return b.length >= 4 && (b[0] & 255) == 255 && (b[1] & 255) == 216
                && (b[2] & 255) == 255 && (b[b.length - 2] & 255) == 255 && (b[b.length - 1] & 255) == 217;
    }
    private boolean isPng(byte[] b) {
        byte[] header = {(byte) 137, 80, 78, 71, 13, 10, 26, 10};
        if (b.length < header.length + PNG_END.length) return false;
        for (int i = 0; i < header.length; i++) if (b[i] != header[i]) return false;
        for (int i = 0; i < PNG_END.length; i++) if (b[b.length - PNG_END.length + i] != PNG_END[i]) return false;
        return true;
    }
    private String extensionOf(String name) {
        if (name == null) return "";
        int dot = name.lastIndexOf('.');
        return dot < 0 || dot == name.length() - 1 ? "" : name.substring(dot + 1).toLowerCase(Locale.ROOT);
    }
}
