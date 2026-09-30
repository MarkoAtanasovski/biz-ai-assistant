package com.bizai.backend;

/** The Python service did not answer in time. Mapped to HTTP 504. */
public class AnalyticsTimeoutException extends RuntimeException {
    public AnalyticsTimeoutException(String message) {
        super(message);
    }
}
