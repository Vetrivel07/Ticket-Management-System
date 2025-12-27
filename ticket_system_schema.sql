-- Drop the database if exists
DROP DATABASE IF EXISTS ticket_system;

-- create a new database called "ticket_system"
CREATE DATABASE ticket_system;

-- use ticket_system database
USE ticket_system;

-- Create "users" table
CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(100) NOT NULL,
  email VARCHAR(100) NULL,
  password VARCHAR(255) NOT NULL,
  role ENUM('employee','responder') NOT NULL,
  firstname VARCHAR(100) NULL,
  lastname  VARCHAR(100) NULL,
  dob       DATE NULL,
  address   TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT uq_users_username UNIQUE (username),
  CONSTRAINT uq_users_email UNIQUE (email)
) ENGINE=InnoDB;

-- create "tickets" table (global)
CREATE TABLE tickets (
  id INT AUTO_INCREMENT PRIMARY KEY,

  user_id INT NOT NULL,          -- employee who posted
  responder_id INT NULL,         -- responder who took it

  title TEXT NOT NULL,
  description TEXT NOT NULL,

  status ENUM('pending','in process','done') NOT NULL DEFAULT 'pending',

  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,

  CONSTRAINT fk_tickets_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,

  CONSTRAINT fk_tickets_responder
    FOREIGN KEY (responder_id) REFERENCES users(id)
    ON DELETE SET NULL
    ON UPDATE CASCADE,

  INDEX idx_tickets_user_created (user_id, created_at),
  INDEX idx_tickets_status_created (status, created_at),
  INDEX idx_tickets_responder_status (responder_id, status)
) ENGINE=InnoDB;


-- create "ticket_responder_state" table
CREATE TABLE ticket_responder_log (
  ticket_id INT NOT NULL,
  responder_id INT NOT NULL,
  status ENUM('declined') NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (ticket_id, responder_id),
  CONSTRAINT fk_trs_ticket
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_trs_responder
    FOREIGN KEY (responder_id) REFERENCES users(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  INDEX idx_trl_responder_status (responder_id, status)
) ENGINE=InnoDB;

-- create "ticket_events" table
CREATE TABLE ticket_events (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,

  ticket_id INT NOT NULL,
  actor_user_id INT NOT NULL,

  event_type ENUM(
    'created',
    'edited',
    'assigned',
    'status_changed',
    'declined',
    'deleted'
  ) NOT NULL,

  from_status ENUM('pending','in_process','done') NULL,
  to_status   ENUM('pending','in_process','done') NULL,

  note VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT fk_events_ticket
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,

  CONSTRAINT fk_events_actor
    FOREIGN KEY (actor_user_id) REFERENCES users(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,

  INDEX idx_events_ticket_time (ticket_id, created_at),
  INDEX idx_events_actor_time (actor_user_id, created_at)
) ENGINE=InnoDB;

-- create "messages" table;
CREATE TABLE messages (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,

  message_type ENUM('direct','alert') NOT NULL DEFAULT 'direct',

  sender_id INT NULL,
  receiver_id INT NOT NULL,

  ticket_id INT NULL,

  subject VARCHAR(200) NOT NULL,
  body TEXT NOT NULL,

  is_read TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT fk_messages_sender
    FOREIGN KEY (sender_id) REFERENCES users(id)
    ON DELETE SET NULL ON UPDATE CASCADE,

  CONSTRAINT fk_messages_receiver
    FOREIGN KEY (receiver_id) REFERENCES users(id)
    ON DELETE CASCADE ON UPDATE CASCADE,

  CONSTRAINT fk_messages_ticket
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
    ON DELETE SET NULL ON UPDATE CASCADE,

  INDEX idx_messages_receiver_read_time (receiver_id, is_read, created_at),
  INDEX idx_messages_receiver_time (receiver_id, created_at)
) ENGINE=InnoDB;



-- ----------
-- changes:
-- ----------

-- 1. Add 'is_active' to users:

ALTER TABLE users
ADD COLUMN is_active TINYINT NOT NULL DEFAULT 1;

-- 2. Add new columns in users:
ALTER TABLE users
  ADD COLUMN phone_e164 VARCHAR(20) NULL AFTER email,
  ADD COLUMN profession VARCHAR(120) NULL AFTER address,
  ADD COLUMN organization VARCHAR(80) NULL AFTER profession,
  ADD COLUMN organization_other VARCHAR(120) NULL AFTER organization;


-- 3. add new columns for address in users:
ALTER TABLE users 
DROP COLUMN address;

ALTER TABLE users
  ADD COLUMN address_line1 VARCHAR(200) NULL AFTER dob,
  ADD COLUMN address_line2 VARCHAR(200) NULL AFTER address_line1,
  ADD COLUMN city VARCHAR(120) NULL AFTER address_line2,
  ADD COLUMN state CHAR(2) NULL AFTER city,
  ADD COLUMN zip_code VARCHAR(10) NULL AFTER state;

