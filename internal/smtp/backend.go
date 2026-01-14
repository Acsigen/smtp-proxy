package smtp

import (
	"github.com/emersion/go-smtp"

	"smtp-proxy/internal/config"
	"smtp-proxy/internal/database"
)

// Backend implements smtp.Backend interface
type Backend struct {
	cfg       *config.Config
	emailRepo *database.EmailRepository
}

// NewBackend creates a new SMTP backend
func NewBackend(cfg *config.Config, emailRepo *database.EmailRepository) *Backend {
	return &Backend{
		cfg:       cfg,
		emailRepo: emailRepo,
	}
}

// NewSession implements smtp.Backend.NewSession
func (b *Backend) NewSession(conn *smtp.Conn) (smtp.Session, error) {
	return NewSession(b.cfg, b.emailRepo, conn), nil
}
