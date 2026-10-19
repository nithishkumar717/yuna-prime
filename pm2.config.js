module.exports = {
  apps: [
    {
      name: "yuna-supreme",
      script: "app.py",
      interpreter: "python3",
      env: {
        ENVIRONMENT: "vps",
        OMP_NUM_THREADS: "1",
        GIT_WEBHOOK_PORT: "2035"
      },
      restart_delay: 3000,
      max_memory_restart: "250M"
    }
  ]
};
