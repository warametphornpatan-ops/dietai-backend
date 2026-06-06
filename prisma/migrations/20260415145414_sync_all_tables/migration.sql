/*
  Warnings:

  - Added the required column `citizen_id` to the `doctors` table without a default value. This is not possible if the table is not empty.

*/
-- AlterTable
ALTER TABLE `doctors` ADD COLUMN `citizen_id` VARCHAR(13) NOT NULL;
