package database

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite"
)

// DB wraps the SQL database connection
type DB struct {
	conn *sql.DB
}

// New creates a new database connection and initializes the schema
func New(path string) (*DB, error) {
	// Ensure the directory exists
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create database directory: %w", err)
	}

	conn, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Test the connection
	if err := conn.Ping(); err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	db := &DB{conn: conn}

	// Initialize schema
	if err := db.initSchema(); err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to initialize schema: %w", err)
	}

	return db, nil
}

// Close closes the database connection
func (db *DB) Close() error {
	return db.conn.Close()
}

// Conn returns the underlying database connection
func (db *DB) Conn() *sql.DB {
	return db.conn
}

// initSchema creates the database tables if they don't exist
func (db *DB) initSchema() error {
	schema := `
		CREATE TABLE IF NOT EXISTS users (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			username TEXT NOT NULL UNIQUE,
			password_hash TEXT NOT NULL,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP
		);

		CREATE TABLE IF NOT EXISTS emails (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			sender TEXT NOT NULL,
			recipients TEXT NOT NULL,
			subject TEXT DEFAULT '',
			body TEXT NOT NULL,
			raw_message BLOB NOT NULL,
			size_bytes INTEGER NOT NULL,
			received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			status TEXT DEFAULT 'received',
			smtp_auth_user TEXT DEFAULT '',
			client_ip TEXT DEFAULT ''
		);

		CREATE INDEX IF NOT EXISTS idx_emails_received_at ON emails(received_at DESC);
		CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender);
		CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
	`

	_, err := db.conn.Exec(schema)
	return err
}
