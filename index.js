const express = require('express');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

function validId(id) {
  return /^[a-zA-Z0-9_-]{1,64}$/.test(id);
}

app.get('/:fbid/file.txt', (req, res) => {
  const fbid = req.params.fbid;
  if (!validId(fbid)) return res.status(400).send('Invalid ID');

  const filePath = path.join(__dirname, 'files', `${fbid}.txt`);
  if (fs.existsSync(filePath)) {
    return res.type('text/plain').send(fs.readFileSync(filePath, 'utf8'));
  }

  const defaultPath = path.join(__dirname, 'files', 'file.txt');
  if (fs.existsSync(defaultPath)) {
    return res.type('text/plain').send(fs.readFileSync(defaultPath, 'utf8'));
  }

  return res.status(404).send('Not found');
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
  console.log(`✅ Server running at http://localhost:${PORT}`);
});
