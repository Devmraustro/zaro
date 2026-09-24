/**
 * ZARO storefront localization — English (canonical), French, Arabic.
 *
 * Strings are keyed once and translated twice; `en` is fallback for any
 * missing key in fr/ar. Interpolation tokens use `{name}` syntax.
 */

export const LANGS = ["en", "fr", "ar"] as const;
export type Lang = (typeof LANGS)[number];

export const DEFAULT_LANG: Lang = "en";
export const LANG_COOKIE = "zaro_lang";

export function isLang(value: unknown): value is Lang {
  return LANGS.includes(value as Lang);
}

export function isRtl(lang: Lang): boolean {
  return lang === "ar";
}

export const LANG_OPTIONS: ReadonlyArray<{ value: Lang; label: string; native: string }> = [
  { value: "en", label: "EN", native: "English" },
  { value: "fr", label: "FR", native: "Français" },
  { value: "ar", label: "AR", native: "العربية" },
];

export interface Dict {
  [key: string]: string;
}

const en: Dict = {
  // Header
  "nav.shop": "Shop",
  "nav.custom": "Custom Order",
  "nav.admin": "Admin",
  "header.startProject": "Start a project",
  "header.openMenu": "Open menu",
  "header.closeMenu": "Close menu",

  // Footer
  "footer.tagline": "Modern furniture and handcrafted metalwork. Built with precision, designed with intention.",
  "footer.collection": "Collection",
  "footer.newArrivals": "New arrivals",
  "footer.bespoke": "Bespoke",
  "footer.customOrder": "Custom Order",
  "footer.trackOrder": "Track your order",
  "footer.studio": "Studio",
  "footer.staffAccess": "Staff access",
  "footer.copyright": "© {year} ZARO Studio — Modern Furniture & Metalwork",
  "footer.madeTagline": "Made, not merely listed",
  "footer.langLabel": "Language",

  // Home
  "home.eyebrow": "Modern furniture & metalwork",
  "home.heroTitleA": "Furniture and metalwork,",
  "home.heroTitleB": "engineered by hand.",
  "home.heroCopy":
    "Precision-built pieces for considered modern interiors — designed with intention, made to last, and made to your specification when the standard isn't enough.",
  "home.ctaShop": "Shop collection",
  "home.ctaCustom": "Custom order",
  "home.statementEyebrow": "The studio",
  "home.statementTitle": "Precision is the foundation. Craft is the finish.",
  "home.statementP1":
    "ZARO designs and builds modern furniture and custom metalwork as a single practice — architecture informs every piece, and every piece is finished by hand.",
  "home.statementP2":
    "The result is a quiet, premium collection: nothing decorative for its own sake, everything resolved in line, material and joinery.",
  "home.exploreCollection": "Explore the collection",
  "home.disciplinesEyebrow": "What we craft",
  "home.disciplinesTitle": "Four disciplines, one studio",
  "home.d1e": "01 — Seating",
  "home.d1t": "Dining Chairs",
  "home.d1c": "Sculptural seats that hold a room — joined, shaped and finished by hand.",
  "home.d2e": "02 — Tables",
  "home.d2t": "Dining & Occasional Tables",
  "home.d2c": "Considered tops on precise frames, in solid timber and blackened steel.",
  "home.d3e": "03 — Metalwork",
  "home.d3t": "Custom Metalwork",
  "home.d3c": "Frames, brackets and architectural steelwork — welded, ground and refined.",
  "home.d4e": "04 — Bespoke",
  "home.d4t": "Custom Furniture",
  "home.d4c": "When the standard piece isn't enough, we build to your exact specification.",
  "home.craftEyebrow": "Craft & materials",
  "home.craftTitle": "Made, not merely listed.",
  "home.craftCopy":
    "Every ZARO piece moves through the same hands — cut, welded, ground and finished in our studio. That is the difference between furniture and objects that are simply sold.",
  "home.p1t": "Designed like architecture",
  "home.p1c": "Proportion, line and load are considered before material is ever cut.",
  "home.p2t": "Built by hand",
  "home.p2c": "Joining, welding and finishing happen in our studio — not on a line.",
  "home.p3t": "Made to your spec",
  "home.p3c": "Dimensions, materials and finish can be tailored to the piece you need.",
  "home.bespokeEyebrow": "Bespoke service",
  "home.bespokeTitle": "Have something specific in mind?",
  "home.bespokeCopy":
    "Tell us about your space, your measurements and your materials. We refine the design, confirm every detail, then build the piece in our studio.",
  "home.startCustomOrder": "Start a custom order",

  // Shop
  "shop.eyebrow": "The collection",
  "shop.title": "Furniture & metalwork",
  "shop.copy": "Every piece is designed in our studio and finished by hand. Filter the collection, or start from your own brief.",
  "shop.searchPlaceholder": "Search the collection",
  "shop.searchAria": "Search products",
  "shop.categoryAria": "Filter by category",
  "shop.allCategories": "All categories",
  "shop.sortAria": "Sort products",
  "shop.sort.newest": "Newest",
  "shop.sort.oldest": "Oldest",
  "shop.sort.name": "Name A–Z",
  "shop.sort.priceAsc": "Price, low to high",
  "shop.sort.priceDesc": "Price, high to low",
  "shop.piece": "piece",
  "shop.pieces": "pieces",
  "shop.error": "The catalog is temporarily unavailable.",
  "shop.emptyTitle": "The collection is being prepared",
  "shop.emptyCopy":
    "New pieces are being crafted in the studio. Until they arrive, tell us what you need — most of our work begins as a conversation.",
  "shop.loading": "Opening the collection",
  "shop.prev": "Previous",
  "shop.next": "Next",

  // Product detail
  "detail.backToCollection": "Back to the collection",
  "detail.unavailable": "This piece is temporarily unavailable.",
  "detail.loading": "Preparing the piece…",
  "detail.breadcrumbCollection": "Collection",
  "detail.dimensions": "Dimensions",
  "detail.materials": "Materials",
  "detail.productionTime": "Production time",
  "detail.days": "{days} days",
  "detail.delivery": "Delivery",
  "detail.deliveryArranged": "Arranged individually",
  "detail.deliveryNotAvailable": "Not available",
  "detail.options": "Options",
  "detail.viewImage": "View image {index} of {count}",
  "detail.requestCustom": "Request a custom version",
  "detail.backToCollection2": "Back to collection",
  "detail.customize": "Customize",
  "detail.studioNote":
    "Every piece is designed and built in the ZARO studio. Sizes, materials and finishes can typically be adjusted to your space.",

  // Custom page
  "custom.eyebrow": "Bespoke service",
  "custom.title": "Furniture designed around you.",
  "custom.intro":
    "Custom work is what ZARO grew from. Tell us what the standard collection can't — and we design and build the piece in our studio, to your exact specification.",
  "custom.r1": "No fixed range — adapt any piece from the collection",
  "custom.r2": "Your dimensions, your materials, your finish",
  "custom.r3": "A clear conversation from first sketch to delivery",
  "custom.howItWorks": "How it works",
  "custom.p1t": "Share your vision",
  "custom.p1c": "Describe the piece, the space and any reference material — dimension, materials, finish, budget.",
  "custom.p2t": "We refine the design",
  "custom.p2c": "Your brief becomes a resolved design: proportions, joinery and finish are confirmed before we build.",
  "custom.p3t": "Precision build",
  "custom.p3c": "The piece is made in our studio — timber cut and joined, steel welded and ground, all finished by hand.",
  "custom.p4t": "Arranged delivery",
  "custom.p4c": "We agree delivery or collection for your finished piece, and confirm every detail along the way.",
  "custom.formTitle": "Start your request",
  "custom.formCopy":
    "No commitment — share as much as you know. A member of the studio reviews every request and replies with next steps.",

  // Order tracking
  "track.eyebrow": "Order tracking",
  "track.title": "Where is your piece?",
  "track.intro":
    "Enter the reference you received when submitting, plus the email or phone used at that time. We check the request and show its current status.",
  "track.referenceLabel": "Request reference",
  "track.referencePlaceholder": "e.g. CR-2026-0001",
  "track.contactLabel": "Email or phone used at submission",
  "track.contactPlaceholder": "e.g. you@example.com or +213 555 00 00 00",
  "track.lookup": "Check status",
  "track.checking": "Checking…",
  "track.errorRequire": "Enter your reference and the email or phone used when submitting.",
  "track.errorGeneric": "We couldn't check that request right now. Please try again in a moment.",
  "track.notFound": "We couldn't find a matching request. Double-check the reference and the contact used when submitting.",
  "track.statusLabel": "Status",
  "track.referenceLabel2": "Reference",
  "track.productTypeLabel": "Type",
  "track.submittedLabel": "Submitted",
  "track.updatedLabel": "Last updated",
  "track.helpLine": "Questions? Quote your reference and contact the studio.",
  "track.st.submitted": "Received",
  "track.st.under_review": "Under review",
  "track.st.needs_information": "More information needed",
  "track.st.quotation_pending": "Quotation being prepared",
  "track.st.cancelled": "Cancelled",
  "track.st.converted": "Converted to an order",
  "track.stCopy.submitted": "Your request has arrived and been logged by the studio.",
  "track.stCopy.under_review": "A member of the studio is reviewing your brief.",
  "track.stCopy.needs_information": "We'll be in touch to confirm a few details.",
  "track.stCopy.quotation_pending": "We're pricing materials and production, then you'll get a quotation.",
  "track.stCopy.cancelled": "This request was cancelled. We're happy to start a new one.",
  "track.stCopy.converted": "Great news — this request has been converted into an order. Someone from the studio will follow up on next steps.",

// Custom request form
  "form.aboutYou": "About you",
  "form.fullName": "Full name",
  "form.email": "Email",
  "form.phone": "Phone",
  "form.productType": "Product type",
  "form.ptDiningTable": "Dining Table",
  "form.ptCoffeeTable": "Coffee Table",
  "form.ptChair": "Chair",
  "form.ptShelf": "Shelf / Storage",
  "form.ptDesk": "Desk",
  "form.ptMetalwork": "Custom Metalwork",
  "form.ptOther": "Other",
  "form.yourProject": "Your project",
  "form.describeProject": "Describe your project",
  "form.describeMin": "min. 10 characters",
  "form.describePlaceholder": "e.g. A 2.4 m oak dining table on a family of six…",
  "form.desiredDimensions": "Desired dimensions",
  "form.dimensionsPlaceholder": "e.g. 200 × 90 × 75 cm",
  "form.quantity": "Quantity",
  "form.materialsBudget": "Materials & budget",
  "form.materials": "Materials",
  "form.materialsPlaceholder": "e.g. solid oak, blackened steel",
  "form.colors": "Colors",
  "form.finish": "Finish",
  "form.budgetMin": "Budget min (DA)",
  "form.budgetMax": "Budget max (DA)",
  "form.validationShort":
    "Please describe your project in at least 10 characters.",
  "form.sending": "Sending…",
  "form.sendRequest": "Send request",
  "form.privacyNote": "We reply to every request. Your details stay within the studio.",
  "form.errorGeneric": "Something went wrong",
  "form.receivedTitle": "Request received",
  "form.receivedCopy":
    "Your reference is {reference}. A member of the studio will review it and reply with next steps.",
  "form.submitAnother": "Submit another request",
  // Location form fields
  "form.country": "Country",
  "form.wilaya": "Wilaya",
  "form.commune": "Commune",
  "form.address": "Address",
  "form.selectWilaya": "Select wilaya",
  "form.selectWilayaFirst": "Select a wilaya first",
  "form.addressPlaceholder": "e.g. 2.4 m oak dining table on a blackened steel base",
};

const fr: Dict = {
  "nav.shop": "Boutique",
  "nav.custom": "Commande sur mesure",
  "nav.admin": "Admin",
  "header.startProject": "Commencer un projet",
  "header.openMenu": "Ouvrir le menu",
  "header.closeMenu": "Fermer le menu",

  "footer.tagline":
    "Mobilier moderne et métallerie artisanale. Conçu avec précision, dessiné avec intention.",
  "footer.collection": "Collection",
  "footer.newArrivals": "Nouvelles pièces",
  "footer.bespoke": "Sur mesure",
  "footer.customOrder": "Commande sur mesure",
  "footer.trackOrder": "Suivre votre commande",
  "footer.studio": "L'atelier",
  "footer.staffAccess": "Accès du personnel",
  "footer.copyright": "© {year} ZARO Studio — Mobilier moderne & métallerie",
  "footer.madeTagline": "Fabriqué, pas simplement catalogué",
  "footer.langLabel": "Langue",

  "home.eyebrow": "Mobilier moderne & métallerie",
  "home.heroTitleA": "Mobilier et métallerie,",
  "home.heroTitleB": "façonnés à la main.",
  "home.heroCopy":
    "Des pièces de précision pour des intérieurs modernes et réfléchis — conçues avec intention, conçues pour durer, et adaptées à votre demande quand le standard ne suffit pas.",
  "home.ctaShop": "Voir la collection",
  "home.ctaCustom": "Sur mesure",
  "home.statementEyebrow": "L'atelier",
  "home.statementTitle": "La précision est la base. Le savoir-faire est la finition.",
  "home.statementP1":
    "ZARO conçoit et fabrique du mobilier moderne et de la métallerie sur mesure comme une seule pratique — l'architecture inspire chaque pièce, et chaque pièce est finie à la main.",
  "home.statementP2":
    "Le résultat est une collection calme et haut de gamme : rien de décoratif pour lui-même, tout est résolu en ligne, en matière et en assemblage.",
  "home.exploreCollection": "Explorer la collection",
  "home.disciplinesEyebrow": "Notre savoir-faire",
  "home.disciplinesTitle": "Quatre disciplines, un seul atelier",
  "home.d1e": "01 — Assises",
  "home.d1t": "Chaises de table",
  "home.d1c": "Des assises sculpturales qui habitent une pièce — assemblées, formées et finies à la main.",
  "home.d2e": "02 — Tables",
  "home.d2t": "Tables de repas & d'appoint",
  "home.d2c": "Des plateaux réfléchis sur des cadres précis, en bois massif et acier noirci.",
  "home.d3e": "03 — Métallerie",
  "home.d3t": "Métallerie sur mesure",
  "home.d3c": "Cadres, consoles et structures acier — soudés, meulés et affinés.",
  "home.d4e": "04 — Sur mesure",
  "home.d4t": "Mobilier sur mesure",
  "home.d4c": "Quand la pièce standard ne suffit pas, nous construisons selon votre spécification exacte.",
  "home.craftEyebrow": "Matières & savoir-faire",
  "home.craftTitle": "Fabriqué, pas simplement catalogué.",
  "home.craftCopy":
    "Chaque pièce ZARO passe entre les mêmes mains — coupée, soudée, meulée et finie dans notre atelier. C'est la différence entre du mobilier et des objets simplement vendus.",
  "home.p1t": "Conçu comme une architecture",
  "home.p1c": "Proportion, ligne et charge sont étudiées avant la première coupe.",
  "home.p2t": "Fabriqué à la main",
  "home.p2c": "Assemblage, soudure et finition se font dans notre atelier — pas sur une chaîne.",
  "home.p3t": "Fait pour votre cahier des charges",
  "home.p3c": "Dimensions, matières et finitions peuvent être adaptées à la pièce dont vous avez besoin.",
  "home.bespokeEyebrow": "Service sur mesure",
  "home.bespokeTitle": "Une idée précise en tête ?",
  "home.bespokeCopy":
    "Parlez-nous de votre espace, de vos mesures et de vos matières. Nous affinons le dessin, confirmons chaque détail, puis fabriquons la pièce dans notre atelier.",
  "home.startCustomOrder": "Lancer une commande sur mesure",

  "shop.eyebrow": "La collection",
  "shop.title": "Mobilier & métallerie",
  "shop.copy":
    "Chaque pièce est dessinée dans notre atelier et finie à la main. Filtrez la collection, ou partez de votre propre brief.",
  "shop.searchPlaceholder": "Rechercher dans la collection",
  "shop.searchAria": "Rechercher des produits",
  "shop.categoryAria": "Filtrer par catégorie",
  "shop.allCategories": "Toutes les catégories",
  "shop.sortAria": "Trier les produits",
  "shop.sort.newest": "Nouveautés",
  "shop.sort.oldest": "Plus anciens",
  "shop.sort.name": "Nom A–Z",
  "shop.sort.priceAsc": "Prix croissant",
  "shop.sort.priceDesc": "Prix décroissant",
  "shop.piece": "pièce",
  "shop.pieces": "pièces",
  "shop.error": "Le catalogue est temporairement indisponible.",
  "shop.emptyTitle": "La collection se prépare",
  "shop.emptyCopy":
    "De nouvelles pièces sont en cours de fabrication à l'atelier. En attendant, dites-nous ce dont vous avez besoin — la plupart de notre travail commence par une conversation.",
  "shop.loading": "Ouverture de la collection",
  "shop.prev": "Précédent",
  "shop.next": "Suivant",

  "detail.backToCollection": "Retour à la collection",
  "detail.unavailable": "Cette pièce est temporairement indisponible.",
  "detail.loading": "Préparation de la pièce…",
  "detail.breadcrumbCollection": "Collection",
  "detail.dimensions": "Dimensions",
  "detail.materials": "Matières",
  "detail.productionTime": "Temps de production",
  "detail.days": "{days} jours",
  "detail.delivery": "Livraison",
  "detail.deliveryArranged": "Convenue individuellement",
  "detail.deliveryNotAvailable": "Non disponible",
  "detail.options": "Options",
  "detail.viewImage": "Voir l'image {index} sur {count}",
  "detail.requestCustom": "Demander une version sur mesure",
  "detail.backToCollection2": "Retour à la collection",
  "detail.customize": "Personnaliser",
  "detail.studioNote":
    "Chaque pièce est dessinée et fabriquée dans l'atelier ZARO. Dimensions, matières et finitions peuvent généralement être adaptées à votre espace.",

  "custom.eyebrow": "Service sur mesure",
  "custom.title": "Du mobilier pensé autour de vous.",
  "custom.intro":
    "Le sur mesure est à l'origine de ZARO. Dites-nous ce que la collection standard ne peut pas — nous dessinons et fabriquons la pièce dans notre atelier, selon votre spécification exacte.",
  "custom.r1": "Aucune gamme figée — adaptez n'importe quelle pièce de la collection",
  "custom.r2": "Vos dimensions, vos matières, vos finitions",
  "custom.r3": "Un échange clair, du premier croquis à la livraison",
  "custom.howItWorks": "Comment ça marche",
  "custom.p1t": "Partagez votre vision",
  "custom.p1c": "Décrivez la pièce, l'espace et vos références — dimensions, matières, finitions, budget.",
  "custom.p2t": "Nous affinons le dessin",
  "custom.p2c": "Votre brief devient un dessin abouti : proportions, assemblages et finitions sont confirmés avant fabrication.",
  "custom.p3t": "Fabrication de précision",
  "custom.p3c": "La pièce est fabriquée dans notre atelier — bois coupé et assemblé, acier soudé et meulé, le tout fini à la main.",
  "custom.p4t": "Livraison organisée",
  "custom.p4c": "Nous convenons de la livraison ou du retrait de votre pièce, et confirmons chaque détail en cours de route.",
  "custom.formTitle": "Commencez votre demande",
  "custom.formCopy":
    "Sans engagement — partagez ce que vous savez. Un membre de l'atelier examine chaque demande et répond avec les prochaines étapes.",

  // Suivi de commande
  "track.eyebrow": "Suivi de commande",
  "track.title": "Où en est votre pièce ?",
  "track.intro":
    "Saisissez la référence reçue lors de la soumission, ainsi que l'e-mail ou le téléphone utilisés à ce moment-là. Nous vérifions la demande et affichons son statut actuel.",
  "track.referenceLabel": "Référence de la demande",
  "track.referencePlaceholder": "ex. CR-2026-0001",
  "track.contactLabel": "E-mail ou téléphone utilisé à la soumission",
  "track.contactPlaceholder": "ex. vous@exemple.com ou +213 555 00 00 00",
  "track.lookup": "Vérifier le statut",
  "track.checking": "Vérification…",
  "track.errorRequire": "Saisissez votre référence et l'e-mail ou le téléphone utilisés lors de la soumission.",
  "track.errorGeneric": "Impossible de vérifier cette demande pour le moment. Réessayez dans un instant.",
  "track.notFound": "Aucune demande correspondante trouvée. Vérifiez la référence et le contact utilisés lors de la soumission.",
  "track.statusLabel": "Statut",
  "track.referenceLabel2": "Référence",
  "track.productTypeLabel": "Type",
  "track.submittedLabel": "Envoyée le",
  "track.updatedLabel": "Mise à jour",
  "track.helpLine": "Des questions ? Citez votre référence et contactez l'atelier.",
  "track.st.submitted": "Reçue",
  "track.st.under_review": "En cours d'examen",
  "track.st.needs_information": "Informations complémentaires requises",
  "track.st.quotation_pending": "Devis en préparation",
  "track.st.cancelled": "Annulée",
  "track.st.converted": "Transformée en commande",
  "track.stCopy.submitted": "Votre demande est arrivée et a été enregistrée par l'atelier.",
  "track.stCopy.under_review": "Un membre de l'atelier examine votre brief.",
  "track.stCopy.needs_information": "Nous vous recontacterons pour confirmer quelques détails.",
  "track.stCopy.quotation_pending": "Nous chiffrons les matériaux et la production, puis vous recevrez un devis.",
  "track.stCopy.cancelled": "Cette demande a été annulée. Nous serons ravis d'en lancer une nouvelle.",
  "track.stCopy.converted":
    "Bonne nouvelle — cette demande a été transformée en commande. Un membre de l'atelier vous indiquera les prochaines étapes.",

  "form.aboutYou": "À propos de vous",
  "form.fullName": "Nom complet",
  "form.email": "E-mail",
  "form.phone": "Téléphone",
  "form.productType": "Type de pièce",
  "form.ptDiningTable": "Table de repas",
  "form.ptCoffeeTable": "Table basse",
  "form.ptChair": "Chaise",
  "form.ptShelf": "Étagère / Rangement",
  "form.ptDesk": "Bureau",
  "form.ptMetalwork": "Métallerie sur mesure",
  "form.ptOther": "Autre",
  "form.yourProject": "Votre projet",
  "form.describeProject": "Décrivez votre projet",
  "form.describeMin": "min. 10 caractères",
  "form.describePlaceholder":
    "ex. Une table de repas en chêne de 2,4 m sur un piètement acier noirci, pour une famille de six…",
  "form.desiredDimensions": "Dimensions souhaitées",
  "form.dimensionsPlaceholder": "ex. 200 × 90 × 75 cm",
  "form.quantity": "Quantité",
  "form.materialsBudget": "Matières & budget",
  "form.materials": "Matières",
  "form.materialsPlaceholder": "ex. chêne massif, acier noirci",
  "form.colors": "Couleurs",
  "form.finish": "Finition",
  "form.budgetMin": "Budget min (DA)",
  "form.budgetMax": "Budget max (DA)",
  "form.validationShort": "Veuillez décrire votre projet en au moins 10 caractères.",
  "form.sending": "Envoi…",
  "form.sendRequest": "Envoyer la demande",
  "form.privacyNote": "Nous répondons à chaque demande. Vos coordonnées restent dans l'atelier.",
  "form.errorGeneric": "Une erreur est survenue",
  "form.receivedTitle": "Demande reçue",
  "form.receivedCopy":
    "Votre référence est {reference}. Un membre de l'atelier l'examinera et vous répondra avec les prochaines étapes.",
  "form.submitAnother": "Soumettre une autre demande",
  // Location form fields
  "form.country": "Pays",
  "form.wilaya": "Wilaya",
  "form.commune": "Commune",
  "form.address": "Adresse",
  "form.selectWilaya": "Sélectionner une wilaya",
  "form.selectWilayaFirst": "Sélectionnez d'abord une wilaya",
  "form.addressPlaceholder": "ex. Une table de repas en chêne de 2,4 m sur un piètement acier noirci",
};

const ar: Dict = {
  "nav.shop": "المتجر",
  "nav.custom": "طلب مخصص",
  "nav.admin": "الإدارة",
  "header.startProject": "ابدأ مشروعك",
  "header.openMenu": "افتح القائمة",
  "header.closeMenu": "أغلق القائمة",

  "footer.tagline": "أثاث عصري وأعمال معدنية حرفية. دقة في الصنع، وعناية في التصميم.",
  "footer.collection": "المجموعة",
  "footer.newArrivals": "وصل حديثاً",
  "footer.bespoke": "حسب الطلب",
  "footer.customOrder": "طلب مخصص",
  "footer.trackOrder": "تتبّع طلبك",
  "footer.studio": "الاستوديو",
  "footer.staffAccess": "دخول الموظفين",
  "footer.copyright": "© {year} استوديو زارو — أثاث عصري وأعمال معدنية",
  "footer.madeTagline": "صُنع بإتقان، لا مجرّد عارض",
  "footer.langLabel": "اللغة",

  "home.eyebrow": "أثاث عصري وأعمال معدنية",
  "home.heroTitleA": "أثاث وأعمال معدنية",
  "home.heroTitleB": "صُنعت يدوياً بإتقان هندسي.",
  "home.heroCopy":
    "قطع فائقة الدقة لمساحات داخلية عصرية مدروسة — مصممة بعناية، مدهونة لتدوم، وتُصنع وفق مواصفاتك حين لا يكفي الجاهز.",
  "home.ctaShop": "تصفّح المجموعة",
  "home.ctaCustom": "طلب مخصص",
  "home.statementEyebrow": "الاستوديو",
  "home.statementTitle": "الدقة هي الأساس، والحِرفة هي اللمسة الأخيرة.",
  "home.statementP1":
    "تصمّم زارو وتصنع الأثاث العصري والأعمال المعدنية المخصصة كممارسة واحدة — العمارة تلهم كل قطعة، وكل قطعة تُكمل يدوياً.",
  "home.statementP2":
    "النتيجة مجموعة هادئة وراقية: لا شيء زخرفي لمجرده، بل كل شيء محسوم في الخط والمادة والوصل.",
  "home.exploreCollection": "استكشف المجموعة",
  "home.disciplinesEyebrow": "ما نصنعه",
  "home.disciplinesTitle": "أربعة تخصصات، استوديو واحد",
  "home.d1e": "١ — الجلوس",
  "home.d1t": "كراسي الطعام",
  "home.d1c": "مقاعد نحتية تحتضن المكان — تصل وتُشكّل وتُنهى يدوياً.",
  "home.d2e": "٢ — الطاولات",
  "home.d2t": "طاولات الطعام والأسطح",
  "home.d2c": "أسطح مدروسة على هياكل دقيقة، من الخشب المصمت والفولاذ المسوَّد.",
  "home.d3e": "٣ — الأعمال المعدنية",
  "home.d3t": "أعمال معدنية مخصصة",
  "home.d3c": "هياكل ودعامات ومنشآت معدنية معمارية — لحاماً وصقلاً وتنعيماً.",
  "home.d4e": "٤ — حسب الطلب",
  "home.d4t": "أثاث مخصص",
  "home.d4c": "حين لا تكفي القطعة الجاهزة، نبني وفق مواصفاتك الدقيقة.",
  "home.craftEyebrow": "الحرفة والمواد",
  "home.craftTitle": "صُنع بإتقان، لا مجرّد عارض.",
  "home.craftCopy":
    "كل قطعة من زارو تمرّ بين الأيدي نفسها — قَصْاً ولحاماً وصقلاً وإنهاءً داخل استوديونا. هذا هو الفرق بين الأثاث والأشياء المباعة فحسب.",
  "home.p1t": "تصميم هندسي معماري",
  "home.p1c": "يُدرَس التناسب والخط والأحمال قبل أي قصّ للمادة.",
  "home.p2t": "صناعة يدوية",
  "home.p2c": "الوصل واللحام واللمسات الأخيرة تتم في استوديونا — لا على خط إنتاج.",
  "home.p3t": "حسب مواصفاتك",
  "home.p3c": "يمكن تخصيص الأبعاد والمواد والتشطيبات حسب القطعة التي تحتاجها.",
  "home.bespokeEyebrow": "خدمة مخصصة",
  "home.bespokeTitle": "لديك فكرة محددة في ذهنك؟",
  "home.bespokeCopy":
    "أخبرنا عن مساحتك وقياساتك وموادك. نصقل التصميم، ونؤكد كل تفصيلة، ثم نصنع القطعة في استوديونا.",
  "home.startCustomOrder": "ابدأ طلباً مخصصاً",

  "shop.eyebrow": "المجموعة",
  "shop.title": "أثاث وأعمال معدنية",
  "shop.copy":
    "كل قطعة تُصمم في استوديونا وتُنهى يدوياً. صفِّ المجموعة، أو ابدأ من فكرتك الخاصة.",
  "shop.searchPlaceholder": "ابحث في المجموعة",
  "shop.searchAria": "ابحث عن المنتجات",
  "shop.categoryAria": "تصفية حسب الفئة",
  "shop.allCategories": "كل الفئات",
  "shop.sortAria": "ترتيب المنتجات",
  "shop.sort.newest": "الأحدث",
  "shop.sort.oldest": "الأقدم",
  "shop.sort.name": "الاسم من أ إلى ي",
  "shop.sort.priceAsc": "السعر، من الأقل",
  "shop.sort.priceDesc": "السعر، من الأعلى",
  "shop.piece": "قطعة",
  "shop.pieces": "قطع",
  "shop.error": "المتجر غير متاح مؤقتاً.",
  "shop.emptyTitle": "المجموعة قيد التحضير",
  "shop.emptyCopy":
    "قطع جديدة قيد الصنع في الاستوديو. وفي الأثناء أخبرنا بما تحتاجه — فمعظم أعمالنا تبدأ من محادثة.",
  "shop.loading": "جارٍ فتح المجموعة",
  "shop.prev": "السابق",
  "shop.next": "التالي",

  "detail.backToCollection": "العودة إلى المجموعة",
  "detail.unavailable": "هذه القطعة غير متاحة مؤقتاً.",
  "detail.loading": "جارٍ تحضير القطعة…",
  "detail.breadcrumbCollection": "المجموعة",
  "detail.dimensions": "الأبعاد",
  "detail.materials": "المواد",
  "detail.productionTime": "مدة الإنتاج",
  "detail.days": "{days} يوم",
  "detail.delivery": "التوصيل",
  "detail.deliveryArranged": "يُتفق عليه بشكل فردي",
  "detail.deliveryNotAvailable": "غير متاح",
  "detail.options": "الخيارات",
  "detail.viewImage": "عرض الصورة {index} من {count}",
  "detail.requestCustom": "اطلب نسخة مخصصة",
  "detail.backToCollection2": "العودة إلى المجموعة",
  "detail.customize": "تخصيص",
  "detail.studioNote":
    "كل قطعة تُصمم وتُصنع في استوديو زارو. يمكن عادةً تعديل المقاسات والمواد والتشطيبات بما يناسب مساحتك.",

  "custom.eyebrow": "خدمة مخصصة",
  "custom.title": "أثاث مصمَّم حولك.",
  "custom.intro":
    "العمل المخصص هو أصل زارو. أخبرنا بما لا تستطيع المجموعة الجاهزة تقديمه — فنصمم ونصنع القطعة في استوديونا وفق مواصفاتك الدقيقة.",
  "custom.r1": "لا نطاق ثابت — عدّل أي قطعة من المجموعة",
  "custom.r2": "أبعادك، موادك، لمساتك النهائية",
  "custom.r3": "حوار واضح من أول رسمة إلى التسليم",
  "custom.howItWorks": "كيف تعمل الخدمة",
  "custom.p1t": "شارك رؤيتك",
  "custom.p1c": "صف القطعة والمساحة وأي مرجع — الأبعاد والمواد والتشطيب والميزانية.",
  "custom.p2t": "نصقل التصميم",
  "custom.p2c": "يتحول موجزك إلى تصميم مكتمل: تُؤكَّد النسب والوصلات والتشطيبات قبل التصنيع.",
  "custom.p3t": "صناعة دقيقة",
  "custom.p3c": "تصنع القطعة في استوديونا — خشب يُقص ويُوصل، وفولاذ يُلحم ويُصقل، وكل ذلك يُنهى يدوياً.",
  "custom.p4t": "تسليم مُرتَّب",
  "custom.p4c": "نتفق على التوصيل أو الاستلام لقطعتك النهائية، ونؤكد كل تفصيلة على الطريق.",
  "custom.formTitle": "ابدأ طلبك",
  "custom.formCopy":
    "بدون أي التزام — شارك بقدر ما تعرف. فريق الاستوديو يراجع كل طلب ويرد بخطواته التالية.",

  // تتبع الطلب
  "track.eyebrow": "تتبع الطلب",
  "track.title": "أين قطعتك؟",
  "track.intro":
    "أدخل الرقم المرجعي الذي استلمته عند التقديم، إلى جانب البريد الإلكتروني أو الهاتف المستخدمين في ذلك الوقت. نتحقق من الطلب ونعرض حالته الحالية.",
  "track.referenceLabel": "الرقم المرجعي للطلب",
  "track.referencePlaceholder": "مثال CR-2026-0001",
  "track.contactLabel": "البريد الإلكتروني أو الهاتف المستخدم عند التقديم",
  "track.contactPlaceholder": "مثال you@example.com أو +213 555 00 00 00",
  "track.lookup": "تحقّق من الحالة",
  "track.checking": "جارٍ التحقق…",
  "track.errorRequire": "أدخل الرقم المرجعي والبريد الإلكتروني أو الهاتف المستخدمين عند التقديم.",
  "track.errorGeneric": "تعذّر علينا التحقق من هذا الطلب حالياً. حاول مرة أخرى بعد قليل.",
  "track.notFound": "لم نعثر على طلب مطابق. تحقّق من الرقم المرجعي ووسيلة الاتصال المستخدمة عند التقديم.",
  "track.statusLabel": "الحالة",
  "track.referenceLabel2": "المرجع",
  "track.productTypeLabel": "النوع",
  "track.submittedLabel": "أُرسل في",
  "track.updatedLabel": "آخر تحديث",
  "track.helpLine": "لديك سؤال؟ اذكر رقمك المرجعي وتواصل مع الاستوديو.",
  "track.st.submitted": "مُستلَم",
  "track.st.under_review": "قيد المراجعة",
  "track.st.needs_information": "بحاجة إلى معلومات إضافية",
  "track.st.quotation_pending": "التسعيرة قيد التحضير",
  "track.st.cancelled": "ملغى",
  "track.st.converted": "تحوّل إلى طلب",
  "track.stCopy.submitted": "وصل طلبك وسجّله الاستوديو.",
  "track.stCopy.under_review": "أحد أعضاء الاستوديو يراجع موجزك.",
  "track.stCopy.needs_information": "سنتواصل معك لتأكيد بعض التفاصيل.",
  "track.stCopy.quotation_pending": "نُسعّر المواد والتصنيع، ثم تصلك التسعيرة.",
  "track.stCopy.cancelled": "أُلغي هذا الطلب. يسعدنا أن نبدأ طلباً جديداً.",
  "track.stCopy.converted": "خبر سار — تحوّل هذا الطلب إلى طلب شراء. سيتواصل معك الاستوديو بالخطوات التالية.",

  "form.aboutYou": "عنك",
  "form.fullName": "الاسم الكامل",
  "form.email": "البريد الإلكتروني",
  "form.phone": "الهاتف",
  "form.productType": "نوع القطعة",
  "form.ptDiningTable": "طاولة طعام",
  "form.ptCoffeeTable": "طاولة قهوة",
  "form.ptChair": "كرسي",
  "form.ptShelf": "رف / تخزين",
  "form.ptDesk": "مكتب",
  "form.ptMetalwork": "أعمال معدنية مخصصة",
  "form.ptOther": "أخرى",
  "form.yourProject": "مشروعك",
  "form.describeProject": "صف مشروعك",
  "form.describeMin": "10 أحرف على الأقل",
  "form.describePlaceholder":
    "مثال: طاولة طعام من خشب البلوط بطول 2.4 م على قاعدة من الفولاذ المسوَّد، لعائلة من ستة أفراد…",
  "form.desiredDimensions": "الأبعاد المطلوبة",
  "form.dimensionsPlaceholder": "مثال: 200 × 90 × 75 سم",
  "form.quantity": "الكمية",
  "form.materialsBudget": "المواد والميزانية",
  "form.materials": "المواد",
  "form.materialsPlaceholder": "مثال: بلوط مصمت، فولاذ مسوَّد",
  "form.colors": "الألوان",
  "form.finish": "التشطيب",
  "form.budgetMin": "الحد الأدنى للميزانية (دج)",
  "form.budgetMax": "الحد الأقصى للميزانية (دج)",
  "form.validationShort": "يرجى وصف مشروعك في 10 أحرف على الأقل.",
  "form.sending": "جارٍ الإرسال…",
  "form.sendRequest": "إرسال الطلب",
  "form.privacyNote": "نرد على كل طلب. تبقى بياناتك داخل الاستوديو.",
  "form.errorGeneric": "حدث خطأ ما",
  "form.receivedTitle": "تم استلام الطلب",
  "form.receivedCopy":
    "رقم مرجعك هو {reference}. سيراجع أحد أعضاء الاستوديو طلبك ويرد بالخطوات التالية.",
  "form.submitAnother": "إرسال طلب آخر",
  // Location form fields
  "form.country": "بلد",
  "form.wilaya": "ولاية",
  "form.commune": "بلدية",
  "form.address": "عنوان",
  "form.selectWilaya": "اختر ولاية",
  "form.selectWilayaFirst": "اختر ولاية أولاً",
  "form.addressPlaceholder": "مثال: طاولة طعام من خشب الأرز مقاس 2.4م على قاعدة من الفولاذ الأسود",
};

export const DICTS: Record<Lang, Dict> = { en, fr, ar };

export function dictFor(lang: Lang): Dict {
  return DICTS[lang];
}

/** Translate a key for a dictionary, falling back to English, with {token} interpolation. */
export function tr(dict: Dict, key: string, vars?: Record<string, string | number>): string {
  let value = dict[key] ?? DICTS.en[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      value = value.replaceAll(`{${k}}`, String(v));
    }
  }
  return value;
}

/** Translate using the canonical English dictionary (server components without a provider). */
export function tEn(key: string, vars?: Record<string, string | number>): string {
  return tr(DICTS.en, key, vars);
}

export function dirFor(lang: Lang): "ltr" | "rtl" {
  return isRtl(lang) ? "rtl" : "ltr";
}