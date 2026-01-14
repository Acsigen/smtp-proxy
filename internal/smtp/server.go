package smtp

import (
	"crypto/tls"
	"fmt"
	"log"
	"time"

	"github.com/emersion/go-smtp"

	"smtp-proxy/internal/config"
	"smtp-proxy/internal/database"
)

// Server wraps the SMTP server
type Server struct {
	server *smtp.Server
	cfg    *config.Config
}

// NewServer creates and configures a new SMTP server
func NewServer(cfg *config.Config, emailRepo *database.EmailRepository) (*Server, error) {
	backend := NewBackend(cfg, emailRepo)

	s := smtp.NewServer(backend)
	s.Addr = cfg.SMTP.Address()
	s.Domain = cfg.SMTP.Domain
	s.ReadTimeout = time.Duration(cfg.SMTP.ReadTimeoutSecs) * time.Second
	s.WriteTimeout = time.Duration(cfg.SMTP.WriteTimeoutSecs) * time.Second
	s.MaxMessageBytes = cfg.SMTP.MaxMessageBytes
	s.MaxRecipients = cfg.SMTP.MaxRecipients
	s.AllowInsecureAuth = cfg.SMTP.AllowInsecureAuth

	// Configure STARTTLS if enabled
	if cfg.SMTP.TLS.Enabled {
		tlsConfig, err := loadTLSConfig(cfg)
		if err != nil {
			return nil, fmt.Errorf("failed to load TLS config: %w", err)
		}
		s.TLSConfig = tlsConfig
	}

	return &Server{
		server: s,
		cfg:    cfg,
	}, nil
}

// loadTLSConfig loads the TLS certificate and key
func loadTLSConfig(cfg *config.Config) (*tls.Config, error) {
	cert, err := tls.LoadX509KeyPair(cfg.SMTP.TLS.CertFile, cfg.SMTP.TLS.KeyFile)
	if err != nil {
		return nil, fmt.Errorf("failed to load certificate: %w", err)
	}

	return &tls.Config{
		Certificates: []tls.Certificate{cert},
		MinVersion:   tls.VersionTLS12,
	}, nil
}

// Start starts the SMTP server
func (s *Server) Start() error {
	log.Printf("Starting SMTP server on %s (domain: %s)", s.server.Addr, s.server.Domain)
	if s.cfg.SMTP.TLS.Enabled {
		log.Printf("STARTTLS enabled")
	}
	if s.cfg.SMTP.Auth.Required {
		log.Printf("Authentication required")
	}
	return s.server.ListenAndServe()
}

// Shutdown gracefully shuts down the SMTP server
func (s *Server) Shutdown() error {
	log.Println("Shutting down SMTP server...")
	return s.server.Close()
}

// Address returns the server address
func (s *Server) Address() string {
	return s.server.Addr
}
