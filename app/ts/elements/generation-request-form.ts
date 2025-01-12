import {CustomElement, Listen} from 'custom-elements-ts';
import {Vc} from "../vc";
import {ImageSpec} from "../models/image-spec";
import {Chipset} from "./chipset";

@CustomElement({
    tag: 'vc-generation-request-form',
    shadow: false,
    style: ``,
    template: require('./generation-request-form.inc'),
})
export class GenerationRequestForm extends HTMLElement {
    $root: HTMLElement
    $header: HTMLElement
    $form: HTMLElement
    $textInput: HTMLTextAreaElement
    $textChips: Chipset
    $styleInput: HTMLInputElement
    $styleChips: Chipset

    vc: Vc;
    spec: ImageSpec;
    expanded = false;

    constructor() {
        super();
    }

    connectedCallback() {
        this.vc = Vc.instance;
        this.$root = this.querySelector('.request-form');

        this.$header = this.$root.querySelector('h2');
        this.$header.addEventListener('click', (e) => {
            if (this.expanded) {
                this.$form.classList.remove('expanded');
                this.$header.querySelector('span').innerHTML = 'expand_more';
                this.expanded = false;
            } else {
                this.$form.classList.add('expanded');
                this.$header.querySelector('span').innerHTML = 'expand_less';
                this.expanded = true;
            }
        });

        this.$form = this.$root.querySelector('form');
        this.$textInput = this.$form.querySelector('.texts .text-input textarea');
        this.$textChips = this.$form.querySelector('.texts vc-chipset');
        this.$styleInput = this.$form.querySelector('.styles .text-input input');
        this.$styleChips = this.$form.querySelector('.styles vc-chipset');
        this.spec = new ImageSpec();
    }

    protected draw() {
        if (!this.spec) {
            return;
        }

        this.$textChips.update(this.spec.texts);
        this.$styleChips.update(this.spec.styles);
    }

    @Listen('keyup', '.texts textarea')
    protected onTextsKeyup(e: KeyboardEvent) {
        if (e.key === 'Enter') {
            e.preventDefault();
            this.addText()
        }
    }

    @Listen('keyup', '.styles input')
    protected onStylesKeyup(e: KeyboardEvent) {
        if (e.key === 'Enter') {
            e.preventDefault();
            this.addStyle()
        }
    }

    @Listen('click', '.actions button')
    protected submit(e: MouseEvent) {
        e.preventDefault();
        this.vc.create(this.spec);
        this.spec = new ImageSpec();
        this.draw();
    }

    @Listen('click', '.texts .text-input button')
    protected onTextsClick(e: MouseEvent) {
        e.preventDefault();
        this.addText();
    }

    @Listen('click', '.styles .text-input button')
    protected onStylesClick(e: MouseEvent) {
        e.preventDefault();
        this.addStyle();
    }

    @Listen('chipset.remove', '.styles vc-chipset')
    protected onStylesRemove(e: any) {
        this.spec.styles.splice(this.spec.styles.indexOf(e.detail), 1);
        this.draw();
    }

    @Listen('chipset.remove', '.texts vc-chipset')
    protected onTextsRemove(e: any) {
        this.spec.texts.splice(this.spec.texts.indexOf(e.detail), 1);
        this.draw();
    }

    protected addText() {
        const value = this.$textInput.value.trim();
        if (value) {
            this.spec.texts.push(value);
            this.$textInput.value = '';
            this.draw();
        }
    }

    protected addStyle() {
        const value = this.$styleInput.value.trim();
        if (value) {
            this.spec.styles.push(value);
            this.$styleInput.value = '';
            this.draw();
        }
    }
}
