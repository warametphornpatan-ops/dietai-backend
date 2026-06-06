-- CreateTable
CREATE TABLE `admins` (
    `admin_id` INTEGER NOT NULL AUTO_INCREMENT,
    `org_code` VARCHAR(50) NOT NULL,
    `citizen_id` VARCHAR(13) NOT NULL,
    `first_name` VARCHAR(100) NOT NULL,
    `last_name` VARCHAR(100) NOT NULL,
    `email` VARCHAR(100) NOT NULL,
    `username` VARCHAR(50) NOT NULL,
    `password_hash` VARCHAR(255) NOT NULL,
    `created_at` TIMESTAMP(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),

    UNIQUE INDEX `username`(`username`),
    PRIMARY KEY (`admin_id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `doctors` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `org_code` VARCHAR(50) NOT NULL,
    `first_name` VARCHAR(100) NOT NULL,
    `last_name` VARCHAR(100) NOT NULL,
    `username` VARCHAR(50) NOT NULL,
    `password_hash` VARCHAR(255) NOT NULL,
    `email` VARCHAR(100) NULL,

    UNIQUE INDEX `username`(`username`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `food_logs` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `user_id` INTEGER NOT NULL,
    `food_name` VARCHAR(255) NOT NULL,
    `calories` INTEGER NULL DEFAULT 0,
    `carbs` INTEGER NULL DEFAULT 0,
    `protein` INTEGER NULL DEFAULT 0,
    `fat` INTEGER NULL DEFAULT 0,
    `image_url` TEXT NULL,
    `created_at` TIMESTAMP(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),

    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `health_records` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `user_id` VARCHAR(50) NOT NULL,
    `systolic` INTEGER NULL,
    `diastolic` INTEGER NULL,
    `pulse` INTEGER NULL,
    `recommendation` TEXT NULL,
    `created_at` DATETIME(0) NULL DEFAULT CURRENT_TIMESTAMP(0),

    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `refresh_tokens` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `user_id` VARCHAR(191) NOT NULL,
    `token_hash` VARCHAR(255) NULL,
    `created_at` DATETIME(0) NULL,
    `expires_at` DATETIME(0) NOT NULL,
    `is_revoked` BOOLEAN NULL,

    UNIQUE INDEX `token_hash`(`token_hash`),
    INDEX `ix_refresh_tokens_id`(`id`),
    INDEX `ix_refresh_tokens_user_id`(`user_id`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `token_blacklist` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `jti` VARCHAR(500) NULL,
    `created_at` DATETIME(0) NULL,
    `expires_at` DATETIME(0) NULL,

    UNIQUE INDEX `ix_token_blacklist_jti`(`jti`),
    INDEX `ix_token_blacklist_id`(`id`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `user` (
    `id` VARCHAR(191) NOT NULL,
    `email` VARCHAR(191) NULL,
    `username` VARCHAR(191) NOT NULL,
    `password` VARCHAR(255) NOT NULL,
    `role` VARCHAR(20) NOT NULL,
    `citizen_id` VARCHAR(13) NULL,
    `firstName` VARCHAR(191) NULL,
    `lastName` VARCHAR(191) NULL,
    `gender` VARCHAR(20) NULL,
    `age` INTEGER NULL,
    `heightCm` FLOAT NULL,
    `weightKg` FLOAT NULL,
    `targetWeightKg` FLOAT NULL,
    `activityLevel` VARCHAR(50) NULL,
    `goal` VARCHAR(100) NULL,
    `healthInfo` TEXT NULL,
    `createdAt` DATETIME(0) NULL DEFAULT CURRENT_TIMESTAMP(0),
    `target_calories` INTEGER NULL DEFAULT 0,
    `target_carbs` INTEGER NULL DEFAULT 0,
    `target_protein` INTEGER NULL DEFAULT 0,
    `target_fat` INTEGER NULL DEFAULT 0,
    `bmr` FLOAT NULL,
    `bmi` FLOAT NULL,

    UNIQUE INDEX `email`(`email`),
    UNIQUE INDEX `username`(`username`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
