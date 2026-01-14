package config

import (
	"encoding/json"
	"fmt"
	"os"
)

// Config holds all application configuration
type Config struct {
	SMTP     SMTPConfig     `json:"smtp"`
	Web      WebConfig      `json:"web"`
	Database DatabaseConfig `json:"database"`
	Admin    AdminConfig    `json:"admin"`
}

// SMTPConfig holds SMTP server configuration
type SMTPConfig struct {
	Host              string     `json:"host"`
	Port              int        `json:"port"`
	Domain            string     `json:"domain"`
	ReadTimeoutSecs   int        `json:"read_timeout_seconds"`
	WriteTimeoutSecs  int        `json:"write_timeout_seconds"`
	MaxMessageBytes   int64      `json:"max_message_bytes"`
	MaxRecipients     int        `json:"max_recipients"`
	AllowInsecureAuth bool       `json:"allow_insecure_auth"`
	TLS               TLSConfig  `json:"tls"`
	Auth              AuthConfig `json:"auth"`
}

// TLSConfig holds TLS certificate configuration
type TLSConfig struct {
	Enabled  bool   `json:"enabled"`
	CertFile string `json:"cert_file"`
	KeyFile  string `json:"key_file"`
}

// AuthConfig holds SMTP authentication configuration
type AuthConfig struct {
	Required bool   `json:"required"`
	Username string `json:"username"`
	Password string `json:"password"`
}

// WebConfig holds web server configuration
type WebConfig struct {
	Host          string `json:"host"`
	Port          int    `json:"port"`
	SessionSecret string `json:"session_secret"`
	SessionName   string `json:"session_name"`
}

// DatabaseConfig holds database configuration
type DatabaseConfig struct {
	Path string `json:"path"`
}

// AdminConfig holds admin user configuration
type AdminConfig struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

// Load reads and parses the configuration file
func Load(path string) (*Config, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("failed to open config file: %w", err)
	}
	defer file.Close()

	var cfg Config
	decoder := json.NewDecoder(file)
	if err := decoder.Decode(&cfg); err != nil {
		return nil, fmt.Errorf("failed to decode config: %w", err)
	}

	if err := cfg.validate(); err != nil {
		return nil, fmt.Errorf("config validation failed: %w", err)
	}

	return &cfg, nil
}

// validate checks the configuration for required fields
func (c *Config) validate() error {
	if c.SMTP.Port <= 0 {
		return fmt.Errorf("smtp.port must be positive")
	}
	if c.Web.Port <= 0 {
		return fmt.Errorf("web.port must be positive")
	}
	if c.Database.Path == "" {
		return fmt.Errorf("database.path is required")
	}
	if c.Admin.Username == "" {
		return fmt.Errorf("admin.username is required")
	}
	if c.Admin.Password == "" {
		return fmt.Errorf("admin.password is required")
	}
	if c.Web.SessionSecret == "" {
		return fmt.Errorf("web.session_secret is required")
	}
	return nil
}

// Address returns the SMTP server address
func (c *SMTPConfig) Address() string {
	return fmt.Sprintf("%s:%d", c.Host, c.Port)
}

// Address returns the web server address
func (c *WebConfig) Address() string {
	return fmt.Sprintf("%s:%d", c.Host, c.Port)
}
