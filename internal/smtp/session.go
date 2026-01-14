package smtp

import (
	"bytes"
	"io"
	"net/mail"
	"strings"

	"github.com/emersion/go-sasl"
	"github.com/emersion/go-smtp"

	"smtp-proxy/internal/config"
	"smtp-proxy/internal/database"
	"smtp-proxy/internal/models"
)

// Session implements smtp.Session and provides authentication
type Session struct {
	cfg           *config.Config
	emailRepo     *database.EmailRepository
	conn          *smtp.Conn
	authenticated bool
	authUser      string
	from          string
	recipients    []string
}

// NewSession creates a new SMTP session
func NewSession(cfg *config.Config, emailRepo *database.EmailRepository, conn *smtp.Conn) *Session {
	return &Session{
		cfg:       cfg,
		emailRepo: emailRepo,
		conn:      conn,
	}
}

// AuthMechanisms returns the list of supported authentication mechanisms
func (s *Session) AuthMechanisms() []string {
	return []string{sasl.Plain}
}

// Auth handles authentication requests
// Uses a named method (authenticatePlain) as callback instead of anonymous function
func (s *Session) Auth(mech string) (sasl.Server, error) {
	return sasl.NewPlainServer(s.authenticatePlain), nil
}

// authenticatePlain is a named function that handles PLAIN authentication
// This approach avoids anonymous functions for better maintainability
func (s *Session) authenticatePlain(identity, username, password string) error {
	if username == s.cfg.SMTP.Auth.Username && password == s.cfg.SMTP.Auth.Password {
		s.authenticated = true
		s.authUser = username
		return nil
	}
	return smtp.ErrAuthFailed
}

// Mail handles the MAIL FROM command
func (s *Session) Mail(from string, opts *smtp.MailOptions) error {
	if s.cfg.SMTP.Auth.Required && !s.authenticated {
		return smtp.ErrAuthRequired
	}
	s.from = from
	return nil
}

// Rcpt handles the RCPT TO command
func (s *Session) Rcpt(to string, opts *smtp.RcptOptions) error {
	if s.cfg.SMTP.Auth.Required && !s.authenticated {
		return smtp.ErrAuthRequired
	}
	if len(s.recipients) >= s.cfg.SMTP.MaxRecipients {
		return &smtp.SMTPError{
			Code:         452,
			EnhancedCode: smtp.EnhancedCode{4, 5, 3},
			Message:      "Too many recipients",
		}
	}
	s.recipients = append(s.recipients, to)
	return nil
}

// Data handles the DATA command and stores the email
func (s *Session) Data(r io.Reader) error {
	if s.cfg.SMTP.Auth.Required && !s.authenticated {
		return smtp.ErrAuthRequired
	}

	rawData, err := io.ReadAll(r)
	if err != nil {
		return err
	}

	subject := extractSubject(rawData)
	body := extractBody(rawData)
	clientIP := extractClientIP(s.conn)

	email := &models.Email{
		Sender:     s.from,
		Recipients: s.recipients,
		Subject:    subject,
		Body:       body,
		RawMessage: rawData,
		SizeBytes:  int64(len(rawData)),
		AuthUser:   s.authUser,
		ClientIP:   clientIP,
		Status:     "received",
	}

	return s.emailRepo.Create(email)
}

// Reset resets the session state for a new message
func (s *Session) Reset() {
	s.from = ""
	s.recipients = nil
}

// Logout handles the QUIT command
func (s *Session) Logout() error {
	return nil
}

// extractSubject parses the email and extracts the Subject header
func extractSubject(rawData []byte) string {
	msg, err := mail.ReadMessage(bytes.NewReader(rawData))
	if err != nil {
		return ""
	}
	return msg.Header.Get("Subject")
}

// extractBody parses the email and extracts the body content
func extractBody(rawData []byte) string {
	msg, err := mail.ReadMessage(bytes.NewReader(rawData))
	if err != nil {
		return string(rawData)
	}

	body, err := io.ReadAll(msg.Body)
	if err != nil {
		return ""
	}
	return string(body)
}

// extractClientIP extracts the client IP address from the connection
func extractClientIP(conn *smtp.Conn) string {
	if conn == nil || conn.Conn() == nil {
		return ""
	}
	addr := conn.Conn().RemoteAddr()
	if addr == nil {
		return ""
	}
	addrStr := addr.String()
	// Remove port from address
	if idx := strings.LastIndex(addrStr, ":"); idx != -1 {
		return addrStr[:idx]
	}
	return addrStr
}
