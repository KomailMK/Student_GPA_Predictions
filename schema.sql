-- =========================================================
-- Database Schema for Student GPA Prediction System
-- Target: MySQL 8.0+ / 9.x / MariaDB
-- =========================================================

CREATE DATABASE IF NOT EXISTS gpa_predictor
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE gpa_predictor;

-- Users table storing verified user accounts with SHA-256 hashed credentials
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    hashed_name VARCHAR(64) NOT NULL,
    hashed_email VARCHAR(64) NOT NULL UNIQUE,
    hashed_password VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_hashed_email (hashed_email),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
