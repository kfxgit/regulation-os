import express from "express";

const app = express();
const port = 3001;

app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "api" });
});

app.listen(port, () => {
  console.log(`api listening on port ${port}`);
});
