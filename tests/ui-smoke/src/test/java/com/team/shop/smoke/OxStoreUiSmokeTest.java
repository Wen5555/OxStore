package com.team.shop.smoke;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.Keys;
import org.openqa.selenium.OutputType;
import org.openqa.selenium.StaleElementReferenceException;
import org.openqa.selenium.TakesScreenshot;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.logging.LogType;
import org.openqa.selenium.logging.LoggingPreferences;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.logging.Level;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class OxStoreUiSmokeTest {
    private static final Duration WAIT_TIMEOUT = Duration.ofSeconds(20);
    private static final String PRODUCT_NAME = "UI 冒烟商品 " + Instant.now().toEpochMilli();
    private static final String BUYER_NAME = "UI 冒烟买家";
    private static final String BUYER_PHONE = uniquePhone();

    private WebDriver driver;
    private WebDriverWait wait;
    private String baseUrl;
    private String adminUsername;
    private String adminPassword;

    @BeforeEach
    void setUp() {
        if (!"true".equalsIgnoreCase(System.getenv("UI_SMOKE_ALLOW_MUTATIONS"))) {
            throw new IllegalStateException(
                    "This end-to-end test publishes and sells a product. Set UI_SMOKE_ALLOW_MUTATIONS=true "
                            + "only for a disposable, isolated test database.");
        }

        baseUrl = requiredEnvironment("UI_SMOKE_BASE_URL");
        adminUsername = environmentOrDefault("UI_SMOKE_ADMIN_USERNAME", "admin");
        adminPassword = requiredEnvironment("UI_SMOKE_ADMIN_PASSWORD");

        ChromeOptions options = new ChromeOptions();
        if (Boolean.parseBoolean(environmentOrDefault("UI_SMOKE_HEADLESS", "true"))) {
            options.addArguments("--headless=new");
        }
        options.addArguments("--window-size=1440,1200", "--no-sandbox", "--disable-dev-shm-usage");

        String driverPath = System.getenv("CHROME_DRIVER_PATH");
        if (driverPath != null && !driverPath.isBlank()) {
            Path executable = Path.of(driverPath.trim()).toAbsolutePath().normalize();
            if (!Files.isRegularFile(executable)) {
                throw new IllegalStateException("CHROME_DRIVER_PATH does not point to a file: " + executable);
            }
            System.setProperty("webdriver.chrome.driver", executable.toString());
        }

        LoggingPreferences logging = new LoggingPreferences();
        logging.enable(LogType.BROWSER, Level.ALL);
        options.setCapability("goog:loggingPrefs", logging);

        driver = new ChromeDriver(options);
        wait = new WebDriverWait(driver, WAIT_TIMEOUT);
    }

    @AfterEach
    void tearDown() {
        if (driver != null) {
            driver.quit();
        }
    }

    @Test
    void buyerCanSubmitIntentAndSellerCanCompleteTheTrade() throws Exception {
        try {
            driver.get(baseUrl + "/admin/login");
            login(adminPassword + "-invalid");
            wait.until(ExpectedConditions.visibilityOfElementLocated(
                    By.cssSelector(".ant-message-notice-content")));
            assertTrue(driver.getCurrentUrl().endsWith("/admin/login"),
                    "An invalid password must not log the seller in");

            login(adminPassword);
            clickButton("登录");
            wait.until(ExpectedConditions.urlMatches(".*/admin/?$"));

            driver.get(baseUrl + "/admin/products/publish");
            fillByLabel("商品名称", PRODUCT_NAME);
            fillByLabel("商品描述", "Selenium UI 冒烟测试商品，请勿用于实际交易。");
            fillByLabel("价格", "1.00");
            driver.findElement(By.cssSelector("input[type='file']"))
                    .sendKeys(createTemporaryPng().toAbsolutePath().toString());
            clickButton("发布商品");
            wait.until(ExpectedConditions.visibilityOfElementLocated(
                    By.xpath("//*[contains(normalize-space(.), '商品发布成功')]")));

            driver.get(baseUrl + "/");
            wait.until(ExpectedConditions.visibilityOfElementLocated(
                    By.xpath("//*[normalize-space(text())='" + PRODUCT_NAME + "']")));
            fillByPlaceholder("请输入您的姓名", BUYER_NAME);
            fillByPlaceholder("请输入11位手机号", BUYER_PHONE);
            clickButton("提交购买意向");

            wait.until(ExpectedConditions.visibilityOfElementLocated(
                    By.xpath("//div[contains(@class,'ant-modal')]//*[contains(normalize-space(.), '购买意向提交成功')]")));
            String intentCode = wait.until(webDriver -> {
                String code = webDriver.findElement(
                        By.cssSelector(".ant-modal-body div[style*='letter-spacing']")).getText().trim();
                return code.isBlank() ? null : code;
            });
            assertFalse(intentCode.isBlank(), "The submission confirmation must show the buyer's token");

            clickButton("查看排队进度");
            wait.until(ExpectedConditions.urlContains("/intent/"));
            wait.until(ExpectedConditions.visibilityOfElementLocated(
                    By.xpath("//*[normalize-space(text())='排队中']")));
            assertTrue(driver.getPageSource().contains(BUYER_NAME),
                    "The intent query page must display the submitted buyer");

            driver.get(baseUrl + "/admin/intents");
            wait.until(ExpectedConditions.visibilityOfElementLocated(
                    By.xpath("//*[normalize-space(text())='" + BUYER_NAME + "']")));
            clickButton("开始处理队首");
            clickButton("确认成功");
            wait.until(ExpectedConditions.visibilityOfElementLocated(
                    By.xpath("//*[normalize-space(text())='暂无排队意向']")));

            driver.get(baseUrl + "/");
            wait.until(ExpectedConditions.visibilityOfElementLocated(
                    By.xpath("//*[contains(normalize-space(.), '目前没有正在出售的商品')]")));
        } catch (Exception | AssertionError failure) {
            saveFailureEvidence(failure);
            throw failure;
        }
    }

    private void login(String password) {
        replaceInput(By.cssSelector("input[autocomplete='username']"), adminUsername);
        replaceInput(By.cssSelector("input[autocomplete='current-password']"), password);
        clickButton("登录");
    }

    private void replaceInput(By locator, String value) {
        WebElement input = wait.until(ExpectedConditions.visibilityOfElementLocated(locator));
        input.click();
        input.sendKeys(Keys.CONTROL, "a");
        input.sendKeys(value);
    }

    private void fillByLabel(String label, String value) {
        By field = By.xpath("//label[normalize-space()='" + label + "']/following::input[1]"
                + " | //label[normalize-space()='" + label + "']/following::textarea[1]");
        wait.until(ExpectedConditions.visibilityOfElementLocated(field)).sendKeys(value);
    }

    private void fillByPlaceholder(String placeholder, String value) {
        wait.until(ExpectedConditions.visibilityOfElementLocated(
                By.cssSelector("input[placeholder='" + placeholder + "']"))).sendKeys(value);
    }

    private void clickButton(String label) {
        wait.until(webDriver -> {
            try {
                WebElement button = webDriver.findElements(By.tagName("button")).stream()
                        .filter(WebElement::isDisplayed)
                        .filter(WebElement::isEnabled)
                        .filter(candidate -> candidate.getText().replaceAll("\\s+", "").equals(label))
                        .sorted((left, right) -> Boolean.compare(
                                "submit".equalsIgnoreCase(right.getAttribute("type")),
                                "submit".equalsIgnoreCase(left.getAttribute("type"))))
                        .findFirst()
                        .orElse(null);
                if (button == null) {
                    return false;
                }
                button.click();
                return true;
            } catch (StaleElementReferenceException ignored) {
                return false;
            }
        });
    }

    private Path createTemporaryPng() throws IOException {
        Path file = Files.createTempFile("oxstore-ui-smoke-", ".png");
        ImageIO.write(new BufferedImage(1, 1, BufferedImage.TYPE_INT_RGB), "png", file.toFile());
        file.toFile().deleteOnExit();
        return file;
    }

    private void saveFailureEvidence(Throwable failure) {
        Path evidenceDirectory = Path.of("target", "ui-smoke-artifacts");
        try {
            Files.createDirectories(evidenceDirectory);
            String timestamp = Long.toString(Instant.now().toEpochMilli());
            ((JavascriptExecutor) driver).executeScript(
                    "document.querySelectorAll('input[type=password], input[autocomplete=current-password]')"
                            + ".forEach(input => { input.value = '[redacted]'; input.type = 'password'; });");
            Files.copy(((TakesScreenshot) driver).getScreenshotAs(OutputType.FILE).toPath(),
                    evidenceDirectory.resolve(timestamp + ".png"));
            Files.writeString(evidenceDirectory.resolve(timestamp + ".txt"),
                    "URL: " + driver.getCurrentUrl() + System.lineSeparator()
                            + "Failure: " + failure + System.lineSeparator()
                            + "Browser logs:" + System.lineSeparator()
                            + driver.manage().logs().get(LogType.BROWSER).getAll());
        } catch (RuntimeException | IOException evidenceFailure) {
            failure.addSuppressed(evidenceFailure);
        }
    }

    private static String uniquePhone() {
        long suffix = Math.floorMod(Instant.now().toEpochMilli(), 100_000_000L);
        return "139" + String.format("%08d", suffix);
    }

    private static String requiredEnvironment(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("Required environment variable is missing: " + name);
        }
        return value.trim();
    }

    private static String environmentOrDefault(String name, String defaultValue) {
        String value = System.getenv(name);
        return value == null || value.isBlank() ? defaultValue : value.trim();
    }
}
