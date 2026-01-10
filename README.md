# Andromica

**Your content. Your rules. Your audience.**

Andromica is a privacy-first platform for creators who want to share their work on their own terms. Create stunning galleries, protect your images from AI scrapers, and distribute directly to your subscribers - no middlemen, no algorithms, no compromises.

---

## Defend Your Art from AI Scraping

AI models are being trained on your images without consent. Most "protection" tools try to poison images covertly - hiding manipulation that breaks AI training. But there's a problem: covert poisoning feels deceptive, and it's an arms race you can't win.

**Andromica takes a different approach: Digital Aposematism.**

In nature, aposematism is warning coloration - the bright colors of poison dart frogs, the patterns on venomous snakes. It says: *"I'm protected. Don't consume me."* It's honest, visible, and effective.

Digital Aposematism applies this principle to your images:

- **Visible transformation** - Protected images are visibly scrambled
- **Ethical approach** - No hidden tricks, just clear signaling
- **Reversible for authorized viewers** - Subscribers see the original
- **AI-hostile by design** - Scrambled images poison training data overtly

When an AI scraper encounters an aposematic image, it gets useless training data. When your subscriber views it, they see your original work. Nature's wisdom, applied to the digital age.

---

## Why Andromica?

Traditional platforms control your content, your audience, and your revenue. Andromica flips the script:

- **You own your content** - stored on IPFS, not corporate servers
- **You choose your audience** - share only with subscribers you approve
- **You control access** - protect images with encryption or visual scrambling
- **You keep the connection** - direct creator-to-subscriber distribution
- **You defend against AI** - Digital Aposematism poisons scrapers, not your audience

---

## Features

### For Creators (Image Mode)

| Feature | Description |
|---------|-------------|
| **Gallery Creation** | Import images, add watermarks, embed metadata |
| **Content Protection** | Encrypt or scramble images for subscriber-only access |
| **IPTC Metadata** | Embed copyright, credits, and licensing info |
| **One-Click Deploy** | Publish to IPFS and Pintheon with a single click |
| **Subscriber Management** | Add trusted recipients for protected content |

### For Subscribers (Browser Mode)

| Feature | Description |
|---------|-------------|
| **Channel Subscriptions** | Follow your favorite creators |
| **Auto-Decryption** | Protected content unlocks automatically |
| **Offline Viewing** | Downloaded galleries work without internet |
| **Beautiful Galleries** | Clean, customizable viewing experience |

---

## Quick Start

### Installation

1. Download the latest release for your platform
2. Install [ImageMagick](https://imagemagick.org/) and [ExifTool](https://exiftool.org/)
3. (Optional) Install [IPFS Desktop](https://docs.ipfs.tech/install/ipfs-desktop/) for decentralized storage
4. Run Andromica!

See [docs/INSTALL.md](docs/INSTALL.md) for detailed instructions.

### Creating Your First Gallery

1. **Switch to Image Mode** (butterfly icon)
2. **Import images** - Click the folder icon to add your images
3. **Process images** - Add watermarks and metadata
4. **Choose protection** (optional):
   - Lock icon = Encrypt (fully scrambled, requires key)
   - Butterfly icon = Aposematic (visually scrambled)
5. **Deploy** - Click cloud icon to publish to Pintheon

### Subscribing to Content

1. **Switch to Browser Mode** (globe icon)
2. **Add Subscription** - Enter the creator's Pintheon URL and IPNS hash
3. **Browse Channels** - Select a channel to view
4. **Enjoy** - Protected content decrypts automatically if you have access

---

## Content Protection

Andromica offers two levels of protection, each serving different purposes:

### Aposematic (AI Defense + Access Control)
Visual scrambling that transforms your image while keeping it valid. This is your primary weapon against AI scraping:

- **Publicly shareable** - Post on social media, websites, anywhere
- **AI-hostile** - Scrapers get poisoned training data
- **Subscriber-reversible** - Authorized viewers see the original
- **Ethically transparent** - Visible protection, no hidden tricks

*Use for: Portfolio previews, social media posts, public galleries*

### Encrypted (Maximum Security)
Full cryptographic protection. Images appear as static noise until decrypted:

- **Complete privacy** - No visual information leaks
- **Cryptographically secure** - Military-grade protection
- **Subscriber-only** - Cannot be shared publicly in any form

*Use for: Premium content, sensitive material, client deliverables*

Both methods use Stellar-based cryptography for secure key exchange between creators and subscribers.

---

## Pintheon Integration

[Pintheon](https://pintheon.com) is the companion hosting platform for Andromica galleries.

### What Pintheon Provides
- IPFS pinning for reliable content availability
- IPNS for updateable gallery addresses
- Simple API for gallery deployment
- CDN-backed content delivery

### Deploying to Pintheon

1. Get your Pintheon access token
2. Configure your node URL in Andromica
3. Click the cloud deploy button
4. Share your gallery link with subscribers!

---

## Use Cases

### AI-Conscious Artists
Share your work publicly without feeding the machine. Aposematic images let you maintain a social media presence while poisoning any scraper that tries to harvest your style. Your followers with Andromica see the real thing.

### Digital Artists
Sell access to high-resolution artwork. Share aposematic previews publicly, encrypted originals with paying subscribers. AI scrapers get nothing useful; your patrons get everything.

### Photographers
Distribute client galleries securely. Each client gets their own encrypted access - no shared passwords needed. Post aposematic versions to your portfolio without fear.

### Content Creators
Build a direct relationship with your audience. No platform taking 30%, no algorithm deciding who sees your work, no AI training on your content without consent.

### NFT Artists
Protect the original while displaying the preview. The aposematic version proves authenticity while the encrypted original stays secure until sale.

---

## Workflow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   IMPORT    │ ──▶ │   PROCESS   │ ──▶ │   PROTECT   │
│   Images    │     │  Watermark  │     │  Encrypt or │
│             │     │  Metadata   │     │  Scramble   │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   ENJOY     │ ◀── │  SUBSCRIBE  │ ◀── │   DEPLOY    │
│   Gallery   │     │  to Channel │     │  to IPFS    │
└─────────────┘     └─────────────┘     └─────────────┘
```

---

## Customization

### Themes
Switch between light and dark modes, or customize colors to match your brand.

### Gallery Templates
Galleries render with clean, responsive HTML that looks great on any device.

### Metadata Templates
Save and reuse IPTC metadata templates for consistent copyright and credit information.

---

## Technical Documentation

For developers and AI assistants:

- [Architecture Overview](docs/ARCHITECTURE.md) - System design and components
- [Encryption Details](docs/ENCRYPTION.md) - Cryptography and content protection
- [Data Structures](docs/DATA_STRUCTURES.md) - JSON schemas and storage format
- [Build Guide](docs/BUILD.md) - Building from source
- [Installation](docs/INSTALL.md) - Detailed setup instructions

---

## FAQ

**Q: How does Digital Aposematism protect against AI?**
A: Aposematic images are visibly scrambled - if an AI scraper ingests them, it gets corrupted training data. Unlike covert poisoning, this is transparent and ethical. The scrambling is reversible only for authorized subscribers with the correct key.

**Q: Can I post aposematic images on social media?**
A: Yes! That's a key use case. Aposematic images are valid image files that display normally (just scrambled). Post them anywhere - Instagram, Twitter, your website. Scrapers get poison; your Andromica subscribers see the original.

**Q: Do I need IPFS to use Andromica?**
A: IPFS is optional but recommended. Without it, you can still create and export galleries manually.

**Q: How do subscribers get access to protected content?**
A: You add them to your subscriber list with their public key. They can then decrypt any content you've shared with them.

**Q: What's the difference between Aposematic and Encrypted?**
A: Aposematic is for public sharing with AI defense - the image is scrambled but shareable. Encrypted is for maximum privacy - the image is noise until decrypted. Use aposematic for portfolios and social media; use encrypted for premium/sensitive content.

**Q: Can I use Andromica without Pintheon?**
A: Yes! You can deploy to any IPFS node or export galleries for manual distribution.

**Q: What image formats are supported?**
A: JPEG, PNG, WebP, and most formats supported by ImageMagick.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/andromica/issues)
- **Documentation**: [docs/](docs/)

---

## License

[Your License Here]

---

*Built with love for creators who believe in owning their work.*
