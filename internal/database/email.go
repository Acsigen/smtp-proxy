package database

import (
	"database/sql"
	"fmt"

	"smtp-proxy/internal/models"
)

// EmailRepository handles email database operations
type EmailRepository struct {
	db *DB
}

// NewEmailRepository creates a new email repository
func NewEmailRepository(db *DB) *EmailRepository {
	return &EmailRepository{db: db}
}

// Create inserts a new email into the database
func (r *EmailRepository) Create(email *models.Email) error {
	recipientsJSON, err := email.RecipientsJSON()
	if err != nil {
		return fmt.Errorf("failed to marshal recipients: %w", err)
	}

	query := `
		INSERT INTO emails (sender, recipients, subject, body, raw_message, size_bytes, status, smtp_auth_user, client_ip)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	result, err := r.db.Conn().Exec(
		query,
		email.Sender,
		recipientsJSON,
		email.Subject,
		email.Body,
		email.RawMessage,
		email.SizeBytes,
		email.Status,
		email.AuthUser,
		email.ClientIP,
	)
	if err != nil {
		return fmt.Errorf("failed to insert email: %w", err)
	}

	id, err := result.LastInsertId()
	if err != nil {
		return fmt.Errorf("failed to get last insert id: %w", err)
	}

	email.ID = id
	return nil
}

// GetByID retrieves an email by its ID
func (r *EmailRepository) GetByID(id int64) (*models.Email, error) {
	query := `
		SELECT id, sender, recipients, subject, body, raw_message, size_bytes, received_at, status, smtp_auth_user, client_ip
		FROM emails
		WHERE id = ?
	`

	email := &models.Email{}
	var recipientsJSON string

	err := r.db.Conn().QueryRow(query, id).Scan(
		&email.ID,
		&email.Sender,
		&recipientsJSON,
		&email.Subject,
		&email.Body,
		&email.RawMessage,
		&email.SizeBytes,
		&email.ReceivedAt,
		&email.Status,
		&email.AuthUser,
		&email.ClientIP,
	)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("email not found")
	}
	if err != nil {
		return nil, fmt.Errorf("failed to query email: %w", err)
	}

	if err := email.ParseRecipientsJSON(recipientsJSON); err != nil {
		return nil, fmt.Errorf("failed to parse recipients: %w", err)
	}

	return email, nil
}

// GetAll retrieves all emails ordered by received_at descending
func (r *EmailRepository) GetAll() ([]*models.Email, error) {
	query := `
		SELECT id, sender, recipients, subject, body, raw_message, size_bytes, received_at, status, smtp_auth_user, client_ip
		FROM emails
		ORDER BY received_at DESC
	`

	rows, err := r.db.Conn().Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query emails: %w", err)
	}
	defer rows.Close()

	return r.scanEmailRows(rows)
}

// UpdateStatus updates the status of an email
func (r *EmailRepository) UpdateStatus(id int64, status string) error {
	query := `UPDATE emails SET status = ? WHERE id = ?`

	result, err := r.db.Conn().Exec(query, status, id)
	if err != nil {
		return fmt.Errorf("failed to update email status: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("email not found")
	}

	return nil
}

// DeleteAll removes all emails from the database
func (r *EmailRepository) DeleteAll() error {
	query := `DELETE FROM emails`

	_, err := r.db.Conn().Exec(query)
	if err != nil {
		return fmt.Errorf("failed to delete emails: %w", err)
	}

	return nil
}

// Count returns the total number of emails
func (r *EmailRepository) Count() (int64, error) {
	query := `SELECT COUNT(*) FROM emails`

	var count int64
	err := r.db.Conn().QueryRow(query).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to count emails: %w", err)
	}

	return count, nil
}

// scanEmailRows scans multiple email rows into a slice
func (r *EmailRepository) scanEmailRows(rows *sql.Rows) ([]*models.Email, error) {
	var emails []*models.Email

	for rows.Next() {
		email := &models.Email{}
		var recipientsJSON string

		err := rows.Scan(
			&email.ID,
			&email.Sender,
			&recipientsJSON,
			&email.Subject,
			&email.Body,
			&email.RawMessage,
			&email.SizeBytes,
			&email.ReceivedAt,
			&email.Status,
			&email.AuthUser,
			&email.ClientIP,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan email row: %w", err)
		}

		if err := email.ParseRecipientsJSON(recipientsJSON); err != nil {
			return nil, fmt.Errorf("failed to parse recipients: %w", err)
		}

		emails = append(emails, email)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating email rows: %w", err)
	}

	return emails, nil
}
