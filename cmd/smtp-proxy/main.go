package main

import (
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"smtp-proxy/internal/config"
	"smtp-proxy/internal/database"
	"smtp-proxy/internal/smtp"
	"smtp-proxy/internal/web"
)

func main() {
	configPath := flag.String("config", "config.json", "Path to configuration file")
	flag.Parse()

	log.SetFlags(log.LstdFlags | log.Lshortfile)
	log.Println("Starting SMTP Proxy...")

	// Load configuration
	cfg, err := config.Load(*configPath)
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}
	log.Printf("Configuration loaded from %s", *configPath)

	// Initialize database
	db, err := database.New(cfg.Database.Path)
	if err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}
	defer db.Close()
	log.Printf("Database initialized at %s", cfg.Database.Path)

	// Initialize repositories
	emailRepo := database.NewEmailRepository(db)
	userRepo := database.NewUserRepository(db)

	// Ensure admin user exists
	err = ensureAdminUser(userRepo, cfg.Admin.Username, cfg.Admin.Password)
	if err != nil {
		log.Fatalf("Failed to ensure admin user: %v", err)
	}

	// Create SMTP server
	smtpServer, err := createSMTPServer(cfg, emailRepo)
	if err != nil {
		log.Fatalf("Failed to create SMTP server: %v", err)
	}

	// Create Web server
	webServer := web.NewServer(cfg, emailRepo, userRepo)

	// Start servers in goroutines
	go startSMTPServer(smtpServer)
	go startWebServer(webServer)

	log.Println("All servers started successfully")
	log.Printf("Web UI available at http://%s", cfg.Web.Address())
	log.Printf("SMTP server listening on %s", cfg.SMTP.Address())

	// Wait for shutdown signal
	waitForShutdown(smtpServer, webServer)
}

// ensureAdminUser creates the admin user if it doesn't exist
func ensureAdminUser(userRepo *database.UserRepository, username, password string) error {
	exists, err := userRepo.Exists(username)
	if err != nil {
		return err
	}

	if exists {
		log.Printf("Admin user '%s' already exists", username)
		return nil
	}

	err = userRepo.Create(username, password)
	if err != nil {
		return err
	}

	log.Printf("Admin user '%s' created", username)
	return nil
}

// createSMTPServer creates the SMTP server, handling TLS configuration gracefully
func createSMTPServer(cfg *config.Config, emailRepo *database.EmailRepository) (*smtp.Server, error) {
	// If TLS is enabled, check if certificates exist
	if cfg.SMTP.TLS.Enabled {
		if !fileExists(cfg.SMTP.TLS.CertFile) || !fileExists(cfg.SMTP.TLS.KeyFile) {
			log.Printf("TLS certificates not found, disabling STARTTLS")
			log.Printf("  To enable STARTTLS, create certificates at:")
			log.Printf("    - %s", cfg.SMTP.TLS.CertFile)
			log.Printf("    - %s", cfg.SMTP.TLS.KeyFile)
			cfg.SMTP.TLS.Enabled = false
			cfg.SMTP.AllowInsecureAuth = true
		}
	}

	return smtp.NewServer(cfg, emailRepo)
}

// fileExists checks if a file exists and is not a directory
func fileExists(path string) bool {
	info, err := os.Stat(path)
	if os.IsNotExist(err) {
		return false
	}
	return !info.IsDir()
}

// startSMTPServer starts the SMTP server
func startSMTPServer(server *smtp.Server) {
	if err := server.Start(); err != nil {
		log.Printf("SMTP server error: %v", err)
	}
}

// startWebServer starts the HTTP server
func startWebServer(server *web.Server) {
	if err := server.Start(); err != nil && err != http.ErrServerClosed {
		log.Printf("Web server error: %v", err)
	}
}

// waitForShutdown waits for interrupt signal and gracefully shuts down servers
func waitForShutdown(smtpServer *smtp.Server, webServer *web.Server) {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	sig := <-sigChan
	log.Printf("Received signal %v, initiating graceful shutdown...", sig)

	// Create shutdown context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Shutdown SMTP server
	if err := smtpServer.Shutdown(); err != nil {
		log.Printf("SMTP server shutdown error: %v", err)
	}

	// Shutdown Web server
	if err := webServer.Shutdown(ctx); err != nil {
		log.Printf("Web server shutdown error: %v", err)
	}

	log.Println("Servers stopped gracefully")
}
