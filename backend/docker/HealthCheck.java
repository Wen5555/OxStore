import java.net.HttpURLConnection;
import java.net.URI;

/** Container readiness probe: current-product query also verifies database access. */
public final class HealthCheck {
    public static void main(String[] args) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) URI.create("http://127.0.0.1:8080/api/products/current").toURL().openConnection();
            connection.setConnectTimeout(2000);
            connection.setReadTimeout(2000);
            if (connection.getResponseCode() != 200) System.exit(1);
        } catch (Exception ignored) {
            System.exit(1);
        } finally {
            if (connection != null) connection.disconnect();
        }
    }
}
