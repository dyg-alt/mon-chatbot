const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');

async function scrapeSite() {
  try {
    const response = await axios.get('https://dygwebagency.com');
    const $ = cheerio.load(response.data);
    
    // Extraire le texte principal
    const content = {
      title: $('title').text(),
      headings: [],
      paragraphs: [],
      links: [],
      fullText: $('body').text().trim()
    };
    
    // Extraire les headings
    $('h1, h2, h3, h4').each((i, el) => {
      content.headings.push($(el).text().trim());
    });
    
    // Extraire les paragraphes
    $('p').each((i, el) => {
      const text = $(el).text().trim();
      if (text.length > 0) {
        content.paragraphs.push(text);
      }
    });
    
    // Extraire les liens
    $('a').each((i, el) => {
      const href = $(el).attr('href');
      const text = $(el).text().trim();
      if (text.length > 0) {
        content.links.push({ text, href });
      }
    });
    
    // Sauvegarder dans un fichier JSON
    fs.writeFileSync('public/siteContent.json', JSON.stringify(content, null, 2));
    console.log('✅ Site scraped successfully! Content saved to public/siteContent.json');
    
  } catch (error) {
    console.error('❌ Error scraping site:', error.message);
  }
}

scrapeSite();
