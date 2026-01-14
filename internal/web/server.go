package web

import (
	"context"
	"encoding/gob"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/sessions"

	"smtp-proxy/internal/config"
	"smtp-proxy/internal/database"
)

func init() {
	// Register int64 type for gob encoding in session cookies
	gob.Register(int64(0))
}

// Server wraps the HTTP server
type Server struct {
	server *http.Server
	cfg    *config.Config
}

// NewServer creates and configures a new HTTP server
func NewServer(cfg *config.Config, emailRepo *database.EmailRepository, userRepo *database.UserRepository) *Server {
	// Create session store
	store := sessions.NewCookieStore([]byte(cfg.Web.SessionSecret))
	store.Options = &sessions.Options{
		Path:     "/",
		MaxAge:   86400, // 24 hours
		HttpOnly: true,
		Secure:   false, // Set to true in production with HTTPS
		SameSite: http.SameSiteLaxMode,
	}

	// Create router and register routes
	mux := http.NewServeMux()
	router := NewRouter(cfg, emailRepo, userRepo, store)
	router.RegisterRoutes(mux)

	server := &http.Server{
		Addr:         cfg.Web.Address(),
		Handler:      mux,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	return &Server{
		server: server,
		cfg:    cfg,
	}
}

// Start starts the HTTP server
func (s *Server) Start() error {
	log.Printf("Starting Web server on %s", s.server.Addr)
	return s.server.ListenAndServe()
}

// Shutdown gracefully shuts down the HTTP server
func (s *Server) Shutdown(ctx context.Context) error {
	log.Println("Shutting down Web server...")
	return s.server.Shutdown(ctx)
}

// Address returns the server address
func (s *Server) Address() string {
	return s.server.Addr
}
