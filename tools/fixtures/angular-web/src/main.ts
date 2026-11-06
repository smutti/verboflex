import {APP_INITIALIZER, Component, importProvidersFrom, inject} from '@angular/core';
import {bootstrapApplication} from '@angular/platform-browser';
import {CommonModule} from '@angular/common';
import {HttpClient, provideHttpClient} from '@angular/common/http';
import {FormControl, FormGroup, ReactiveFormsModule, Validators} from '@angular/forms';
import {RouterOutlet, provideRouter, withHashLocation} from '@angular/router';
import {TranslateLoader, TranslateModule, TranslateService} from '@ngx-translate/core';
import {TranslateHttpLoader} from '@ngx-translate/http-loader';
import {firstValueFrom} from 'rxjs';

@Component({standalone:true, imports:[CommonModule, TranslateModule], template:`
  <main data-capture-ready="sites.list" *ngIf="sites">
    <h1 data-key="NAV.SITES">{{'NAV.SITES' | translate}}</h1>
    <div class="map" aria-label="Simulated map">Synthetic map fixture</div>
    <label>{{'SITE.SEARCH' | translate}}<input id="search-site" [placeholder]="'SITE.SEARCH' | translate"></label>
    <table><thead><tr><th data-key="SITE.NAME">{{nameHeading}}</th><th>{{'SITE.ADDRESS' | translate}}</th></tr></thead>
    <tbody><tr *ngFor="let site of sites"><td>{{site.name}}</td><td>{{site.address}}</td></tr></tbody></table>
  </main>`})
class Sites {
  private http=inject(HttpClient); private ts=inject(TranslateService);
  nameHeading=this.ts.instant('SITE.NAME');
  sites: {name:string,address:string}[]|null=null;
  constructor(){this.http.get<{name:string,address:string}[]>('/api/sites').subscribe(v=>this.sites=v);}
}
@Component({standalone:true, imports:[CommonModule, TranslateModule, ReactiveFormsModule], template:`
  <main data-capture-ready="tenants" *ngIf="ready">
    <h1>{{'TENANT.LIST' | translate}}</h1><button id="create-tenant" (click)="open=true">{{'TENANT.CREATE' | translate}}</button>
    <div class="backdrop" *ngIf="open"><section role="dialog" aria-modal="true" [attr.aria-label]="'TENANT.CREATE' | translate" class="dialog">
      <h2 data-key="TENANT.CREATE">{{'TENANT.CREATE' | translate}}</h2>
      <form [formGroup]="form" (ngSubmit)="save()">
        <label>{{'TENANT.EMAIL' | translate}}<input id="email" type="email" formControlName="email"></label>
        <label>{{'TENANT.FIRST_NAME' | translate}}<input id="first-name" formControlName="firstName"></label>
        <p id="first-name-validator" data-key="VALIDATE.MAX_LENGTH" role="alert" *ngIf="form.controls.firstName.errors?.['maxlength'] && (form.controls.firstName.dirty || form.controls.firstName.touched)">{{'VALIDATE.MAX_LENGTH' | translate:{value:form.controls.firstName.errors?.['maxlength']} }}</p>
        <footer><button type="button" id="close" (click)="open=false">{{'GLOBAL.CANCEL' | translate}}</button><button type="submit" id="save" [disabled]="form.invalid">{{'GLOBAL.SAVE' | translate}}</button></footer>
      </form>
    </section></div>
  </main>`})
class Tenants {
  private http=inject(HttpClient); ready=false; open=false;
  form=new FormGroup({email:new FormControl('fixture@example.test',[Validators.required,Validators.email]),firstName:new FormControl('Sample',[Validators.maxLength(97)])});
  constructor(){this.http.get('/api/tenants').subscribe(()=>this.ready=true);}
  save(){if(this.form.valid)this.http.post('/api/tenants',this.form.value).subscribe(()=>this.open=false);}
}
@Component({selector:'app-root',standalone:true,imports:[RouterOutlet],template:`<header>Synthetic property portal</header><router-outlet/>`})
class App {}
function initialize(ts:TranslateService,http:HttpClient){return async()=>{const locale=localStorage.getItem('language') || 'en';ts.setDefaultLang('en');await firstValueFrom(ts.use(locale));await firstValueFrom(http.get('/api/profile'));document.documentElement.lang=locale;};}
bootstrapApplication(App,{providers:[provideHttpClient(),provideRouter([{path:'sites',component:Sites},{path:'sites/:id/tenants',component:Tenants}],withHashLocation()),importProvidersFrom(TranslateModule.forRoot({loader:{provide:TranslateLoader,useFactory:(http:HttpClient)=>new TranslateHttpLoader(http,'/assets/i18n/','.json'),deps:[HttpClient]}})),{provide:APP_INITIALIZER,multi:true,useFactory:initialize,deps:[TranslateService,HttpClient]}]}).catch(error=>console.error(error));
