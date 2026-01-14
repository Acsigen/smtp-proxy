package models

import (
	"encoding/json"
	"time"
)

// Email represents a received email message
type Email struct {
	ID         int64     `json:"id"`
	Sender     string    `json:"sender"`
	Recipients []string  `json:"recipients"`
	Subject    string    `json:"subject"`
	Body       string    `json:"body"`
	RawMessage []byte    `json:"raw_message"`
	SizeBytes  int64     `json:"size_bytes"`
	ReceivedAt time.Time `json:"received_at"`
	Status     string    `json:"status"`
	AuthUser   string    `json:"auth_user"`
	ClientIP   string    `json:"client_ip"`
}

// RecipientsJSON returns the recipients as a JSON string for database storage
func (e *Email) RecipientsJSON() (string, error) {
	data, err := json.Marshal(e.Recipients)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// ParseRecipientsJSON parses a JSON string into the recipients slice
func (e *Email) ParseRecipientsJSON(data string) error {
	return json.Unmarshal([]byte(data), &e.Recipients)
}

// RecipientsDisplay returns a comma-separated string of recipients for display
func (e *Email) RecipientsDisplay() string {
	if len(e.Recipients) == 0 {
		return ""
	}
	result := e.Recipients[0]
	for i := 1; i < len(e.Recipients); i++ {
		result += ", " + e.Recipients[i]
	}
	return result
}

// IsRead returns true if the email has been marked as read
func (e *Email) IsRead() bool {
	return e.Status == "read"
}

// IsNew returns true if the email status is "received" (unread)
func (e *Email) IsNew() bool {
	return e.Status == "received"
}
