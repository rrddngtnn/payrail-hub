const RAIL_HINTS = {
  upi: 'Share the resulting UPI link with an India-region payer (PhonePe / GPay / Paytm).',
  ideal: 'Open or share the resulting iDEAL link with a Netherlands bank payer (EUR).',
  pix: 'Share the resulting Pix link/QR with a Brazil payer (BRL).',
  gopay: 'Share the resulting GoPay link with an Indonesia payer (IDR).',
  momo: 'Share the resulting MoMo link with a Vietnam payer (VND).',
};

/**
 * Usage copy for PayRail Hub embed components.
 */
export function gptToolUsageBundle(language = 'en', tool = 'upiLink', rail = 'upi') {
  if (tool !== 'upiLink') {
    return { title: 'Usage', lines: [] };
  }
  const railKey = String(rail || 'upi').toLowerCase();
  const lines = [
    'Sign in to the site first.',
    'Paste a full Session JSON that includes accessToken and sessionToken.',
    'Extraction usually takes 30–90 seconds; keep the page open until it finishes.',
    RAIL_HINTS[railKey] || `Share the resulting ${railKey.toUpperCase()} payment link with a local payer.`,
  ];
  return {
    title: 'How to use',
    lines,
  };
}

export default gptToolUsageBundle;
