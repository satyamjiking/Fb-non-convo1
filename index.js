const express = require("express");
const path = require("path");
const app = express();

// Public folder ko static serve karna
app.use(express.static(path.join(__dirname, "public")));

// Default route
app.get("/", (req, res) => {
  res.send("🚀 Server chal raha hai Render par!");
});

// Render apna khud ka port deta hai
const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
  console.log(`✅ Server running at http://localhost:${PORT}`);
});
