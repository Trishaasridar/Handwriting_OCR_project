-- Handwriting OCR Application v2 - Database Setup
-- Updated: March 11, 2026

-- Create database (if not exists)
CREATE DATABASE IF NOT EXISTS ocr_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Use the database
USE ocr_db;

-- Create application user (adjust password as needed)
CREATE USER IF NOT EXISTS 'ocr_user'@'%' IDENTIFIED BY 'ocr_password_2026';
GRANT ALL PRIVILEGES ON ocr_db.* TO 'ocr_user'@'%';
FLUSH PRIVILEGES;

-- Create main OCR results table
CREATE TABLE IF NOT EXISTS ocr_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_name VARCHAR(255) NOT NULL,
    course_name VARCHAR(255) NOT NULL,
    image_blob LONGBLOB NOT NULL,
    date DATE NOT NULL,
    time TIME NOT NULL,
    content TEXT,
    confidence_score FLOAT,
    processing_time FLOAT,
    quality_score FLOAT DEFAULT 0.0,
    word_count INT DEFAULT 0,
    text_length INT DEFAULT 0,
    ocr_version VARCHAR(50) DEFAULT '2.0.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Indexes for performance
    INDEX idx_student_course (student_name, course_name),
    INDEX idx_date (date),
    INDEX idx_confidence (confidence_score),
    INDEX idx_created_at (created_at),

    -- Fulltext search index
    FULLTEXT idx_content (content)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create processing statistics table
CREATE TABLE IF NOT EXISTS processing_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    total_requests INT DEFAULT 0,
    successful_requests INT DEFAULT 0,
    failed_requests INT DEFAULT 0,
    avg_processing_time FLOAT DEFAULT 0.0,
    avg_confidence_score FLOAT DEFAULT 0.0,
    total_images_processed INT DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create user sessions table (for future authentication)
CREATE TABLE IF NOT EXISTS user_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id INT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert initial stats record
INSERT IGNORE INTO processing_stats (id, total_requests, successful_requests, failed_requests)
VALUES (1, 0, 0, 0);

-- Create view for recent results
CREATE OR REPLACE VIEW recent_results AS
SELECT
    id,
    student_name,
    course_name,
    date,
    time,
    confidence_score,
    processing_time,
    quality_score,
    word_count,
    text_length,
    created_at
FROM ocr_results
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
ORDER BY created_at DESC;

-- Create stored procedure for updating stats
DELIMITER //

CREATE PROCEDURE update_processing_stats(
    IN success BOOLEAN,
    IN processing_time FLOAT,
    IN confidence_score FLOAT
)
BEGIN
    UPDATE processing_stats
    SET
        total_requests = total_requests + 1,
        successful_requests = IF(success, successful_requests + 1, successful_requests),
        failed_requests = IF(NOT success, failed_requests + 1, failed_requests),
        avg_processing_time = (
            (avg_processing_time * (total_requests - 1)) + processing_time
        ) / total_requests,
        avg_confidence_score = IF(
            confidence_score > 0,
            ((avg_confidence_score * (successful_requests - IF(success, 0, 1))) + confidence_score)
                / successful_requests,
            avg_confidence_score
        ),
        total_images_processed = total_images_processed + IF(success, 1, 0)
    WHERE id = 1;
END //

DELIMITER ;

-- Insert sample data for testing (optional)
-- Uncomment the following lines to add sample data

/*
INSERT INTO ocr_results
(student_name, course_name, image_blob, date, time, content, confidence_score, processing_time, quality_score, word_count, text_length)
VALUES
('John Doe', 'Computer Science 101', '', '2026-03-11', '14:30:00',
 'This is a sample OCR result for testing purposes.', 0.85, 2.3, 0.82, 8, 52),
('Jane Smith', 'Mathematics 201', '', '2026-03-11', '15:45:00',
 'Advanced calculus and differential equations.', 0.92, 1.8, 0.89, 5, 42);
*/

-- Create backup procedure (optional)
DELIMITER //

CREATE PROCEDURE create_backup(IN backup_name VARCHAR(255))
BEGIN
    SET @sql = CONCAT(
        'CREATE TABLE ', backup_name, ' AS SELECT * FROM ocr_results'
    );
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
END //

DELIMITER ;

-- Add comments for documentation
ALTER TABLE ocr_results COMMENT 'Main table storing OCR processing results and image data';
ALTER TABLE processing_stats COMMENT 'Statistics and metrics for OCR processing performance';
ALTER TABLE user_sessions COMMENT 'User session management for future authentication features';

-- Optimize table settings
SET GLOBAL innodb_buffer_pool_size = 134217728; -- 128MB
SET GLOBAL innodb_log_file_size = 33554432; -- 32MB

-- Final flush
FLUSH PRIVILEGES;