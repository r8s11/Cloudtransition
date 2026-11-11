const mode = document.currentScript.dataset.mode;
let step = 1;
document.body.dataset.nextClicks = '0';
document.body.dataset.submitClicks = '0';
function render() {
  const last = mode === 'twelve' ? 12 : 4;
  const labels = ['First name', 'Last name', 'Email'];
  document.querySelector('main').innerHTML = `<h1>${step === last ? 'Review' : `Application step ${step}`}</h1>${step === last ? '' : `<label>${labels[(step-1)%3]}<input required></label>`}<button ${step === last ? 'id="submit"' : 'data-automation-id="bottom-navigation-next-button"'}>${step === last ? 'Submit application' : 'Next'}</button>`;
  document.querySelector('main button').onclick = () => {
    if (step === last) {
      document.body.dataset.submitClicks = String(+document.body.dataset.submitClicks + 1);
      document.querySelector('main').innerHTML = '<h1>Thank you for applying</h1>';
    } else {
      document.body.dataset.nextClicks = String(+document.body.dataset.nextClicks + 1);
      if (mode !== 'validation') step++;
      render();
      if (mode === 'validation') document.querySelector('main').insertAdjacentHTML('beforeend', '<p role="alert">Please check this step</p>');
    }
  };
}
render();
