import express from 'express';
import Anthropic from '@anthropic-ai/sdk';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const client = new Anthropic();

app.use(express.json({ limit: '10mb' }));
app.use(express.static(path.join(__dirname, 'public')));

// ── Narrator Commentary Endpoint ─────────────────────────────────────────────

app.post('/api/narrator', async (req, res) => {
  const { text, pageNumber, totalSpreads, bookTitle } = req.body;

  if (!text || !text.trim()) {
    return res.status(400).json({ error: 'No text provided' });
  }

  const progress = totalSpreads > 1 ? pageNumber / totalSpreads : 0.5;
  let positionHint;
  if (progress < 0.2)       positionHint = 'near the very beginning — things are just getting started';
  else if (progress < 0.4)  positionHint = 'we are getting into the heart of the story now';
  else if (progress < 0.6)  positionHint = 'we are well into the story, past the halfway point';
  else if (progress < 0.8)  positionHint = 'the story is building toward its conclusion';
  else                       positionHint = 'we are approaching the very end of the story';

  const prompt = `You are a warm, beloved storyteller narrator — like a favourite grandparent or gifted teacher — reading a book aloud to a listener. You have just finished reading the following passage aloud:

"${text.slice(0, 450)}"

This is page spread ${pageNumber} of ${totalSpreads} — ${positionHint}.${bookTitle && bookTitle !== 'Your Story' ? ` The book is called "${bookTitle}".` : ''}

Generate a SHORT narrator comment (2–3 sentences maximum) to gently engage the listener between page turns. Be warm, natural, and conversational. Vary your style — sometimes wonder, sometimes anticipation, sometimes gentle reflection, sometimes a touch of humour.

Examples of good tone:
- "Oh, I didn't expect that! I wonder what it means for what comes next... shall we find out?"
- "Isn't that a remarkable thing? Let's keep going — I have a feeling we're in for a surprise."
- "Things are certainly getting interesting now! Come along, let's turn the page."
- "What do you make of all that? I find myself wanting to know what happens next."

Be specific to the passage just read — don't be generic. Keep it brief and let the story breathe.
Output only the commentary itself — no labels, no quotation marks.`;

  try {
    const message = await client.messages.create({
      model: 'claude-opus-4-6',
      max_tokens: 120,
      messages: [{ role: 'user', content: prompt }],
    });

    const commentary = message.content[0].text.trim();
    res.json({ commentary });
  } catch (err) {
    console.error('[Narrator API]', err.message);
    // Warm fallback lines so the show always goes on
    const fallbacks = [
      "Oh my, what a passage! I wonder what's going to happen next... shall we turn the page and find out?",
      "Isn't that something! Let's keep reading — I have a feeling there are surprises ahead of us.",
      "Well, well, well! Things are certainly developing now. Come along, let's see what unfolds next.",
      "What do you think about all of that? Remarkable! Let's not dawdle — onward we go!",
      "Oh, I didn't expect that at all! Let's keep reading and see where this takes us.",
    ];
    res.json({ commentary: fallbacks[Math.floor(Math.random() * fallbacks.length)] });
  }
});

// ── Start ─────────────────────────────────────────────────────────────────────

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`\n📖  Animated Storybook Narrator`);
  console.log(`    http://localhost:${PORT}\n`);
  console.log(`    Upload any text file and watch it come alive!\n`);
});
